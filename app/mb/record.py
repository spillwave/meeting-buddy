import pyaudio
import wave
import asyncio
import os
import sys
from typing import Optional

from app import logger
from app.mb.config import Config
from app import logger, WATCH_DIRECTORY

class AudioRecorder:
    """Handles audio recording functionality."""
    
    def __init__(self):
        self.stream: Optional[pyaudio.Stream] = None
        self.p_audio: Optional[pyaudio.PyAudio] = None
        self.recording = False
        self.config = Config.load_config()
        self._stop_recording = asyncio.Event()
        self.input_device_index = self._get_active_input_device()

    def _get_active_input_device(self) -> Optional[int]:
        """Get the index of the currently active input device."""
        try:
            p = pyaudio.PyAudio()
            # Get all available input devices
            input_devices = []
            default_index = p.get_default_input_device_info()['index']
            default_name = p.get_default_input_device_info()['name']
            logger.info(f"System default input device [{default_index}]: {default_name}")
            
            for i in range(p.get_device_count()):
                try:
                    device_info = p.get_device_info_by_index(i)
                    if device_info.get('maxInputChannels', 0) > 0:  # This is an input device
                        input_devices.append(device_info)
                        logger.info(f"Found input device [{i}]: {device_info['name']} "
                                  f"(channels: {device_info['maxInputChannels']}, "
                                  f"rate: {int(device_info['defaultSampleRate'])})")
                except Exception as e:
                    logger.warning(f"Error getting info for device {i}: {e}")
            
            if not input_devices:
                raise RuntimeError("No input devices found")
            
            # First check if there's an active USB audio device
            for device in input_devices:
                if ('usb' in device['name'].lower() and 
                    device['maxInputChannels'] > 0 and 
                    device['defaultSampleRate'] >= self.config.audio_rate):
                    logger.info(f"Selected USB input device [{device['index']}]: {device['name']}")
                    return device['index']
            
            # If no USB device found, use system default
            logger.info(f"No suitable USB device found, using system default: {default_name}")
            return default_index
            
        except Exception as e:
            logger.error(f"Error finding input device: {e}")
            return None
        finally:
            try:
                p.terminate()
            except Exception as e:
                logger.error(f"Error terminating PyAudio in device detection: {e}")
    
    async def record_audio(self, file_name: str, format=pyaudio.paInt16):
        """Record audio asynchronously."""
        if self._stop_recording.is_set():
            logger.info("Skipping recording due to stop event")
            return

        self.p_audio = pyaudio.PyAudio()
        try:
            # Get device info before opening stream
            device_index = self.input_device_index
            if device_index is None:
                device_index = self.p_audio.get_default_input_device_info()['index']
            
            device_info = self.p_audio.get_device_info_by_index(device_index)
            device_channels = min(int(device_info['maxInputChannels']), self.config.audio_channels)
            device_rate = int(device_info['defaultSampleRate'])
            
            logger.info(f"Opening audio stream for device [{device_index}]: {device_info['name']}")
            logger.info(f"Device config - Channels: {device_channels}, Rate: {device_rate}")
            
            self.stream = self.p_audio.open(
                format=format,
                channels=device_channels,
                rate=device_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.config.audio_chunk_size
            )
            logger.info(f"Successfully opened audio stream")
        except Exception as e:
            logger.error(f"Error opening audio stream: {e}")
            raise

        logger.info(f"Recording: {file_name}")
        frames = []

        try:
            self.recording = True
            total_chunks = int(self.config.audio_rate / self.config.audio_chunk_size * self.config.chunk_record_duration)
            
            for i in range(total_chunks):

                if self._stop_recording.is_set():
                    logger.info("Stop event detected during recording. Finishing this segment before stopping. Chunks left")

                try:
                    # Use asyncio.to_thread for the blocking read operation
                    data = await asyncio.to_thread(
                        self.stream.read,
                        self.config.audio_chunk_size,
                        exception_on_overflow=False
                    )
                    frames.append(data)

                except IOError as e:
                    logger.error(f"IOError during recording: {e}")
                    break

            if frames:  # Only save if we have recorded data
                print(f"* Done recording: {file_name}")
                sample_size = self.p_audio.get_sample_size(format)
                
                wf = wave.open(file_name, 'wb')
                wf.setnchannels(self.config.audio_channels)
                wf.setsampwidth(sample_size)
                wf.setframerate(self.config.audio_rate)
                wf.writeframes(b''.join(frames))
                wf.close()


        finally:
            self._cleanup_audio()

    def _cleanup_audio(self):
        """Clean up audio resources."""
        logger.info("Starting audio resource cleanup")
        cleanup_errors = []
        
        try:
            if self.stream:
                logger.info("Cleaning up audio stream...")
                try:
                    logger.debug("Stopping stream...")
                    self.stream.stop_stream()
                    logger.debug("Stream stopped")
                except Exception as e:
                    err_msg = f"Error stopping stream: {e}"
                    logger.error(err_msg, exc_info=True)
                    cleanup_errors.append(err_msg)
                
                try:
                    logger.debug("Closing stream...")
                    self.stream.close()
                    logger.debug("Stream closed")
                except Exception as e:
                    err_msg = f"Error closing stream: {e}"
                    logger.error(err_msg, exc_info=True)
                    cleanup_errors.append(err_msg)
                
                self.stream = None
                logger.info("Audio stream cleanup completed")
            
            if self.p_audio:
                logger.info("Cleaning up PyAudio...")
                try:
                    self.p_audio.terminate()
                    logger.debug("PyAudio terminated")
                except Exception as e:
                    err_msg = f"Error terminating PyAudio: {e}"
                    logger.error(err_msg, exc_info=True)
                    cleanup_errors.append(err_msg)
                
                self.p_audio = None
                logger.info("PyAudio cleanup completed")
            
            self.recording = False
            logger.info("Recording flag reset")
            
        except Exception as e:
            err_msg = f"Unexpected error in cleanup: {e}"
            logger.error(err_msg, exc_info=True)
            cleanup_errors.append(err_msg)
        finally:
            # Ensure flags are reset even if cleanup fails
            self.stream = None
            self.p_audio = None
            self.recording = False
            
            if cleanup_errors:
                logger.error(f"Cleanup completed with {len(cleanup_errors)} errors: {'; '.join(cleanup_errors)}")
            else:
                logger.info("Audio cleanup completed successfully")

    @staticmethod
    def get_next_file_number(output_dir):
        """Get the next available file number by checking existing files."""
        existing_files = [f for f in os.listdir(output_dir) if f.startswith('recording_') and f.endswith('.wav')]
        if not existing_files:
            return 1
        numbers = [int(f.split('_')[1].split('.')[0]) for f in existing_files]
        return max(numbers) + 1

    async def stop_recording(self):
        """Stop the recording process cleanly."""
        logger.info("Recording service stopping...")
        try:
            self._stop_recording.set()
            self.recording = False
            logger.info("Recording flags set to stop")

            # Force stop any active recording
            if self.stream or self.p_audio:
                try:
                    # Run cleanup in thread to avoid blocking
                    logger.info("Starting audio cleanup in thread...")
                    await asyncio.to_thread(self._cleanup_audio)
                    logger.info("Audio cleanup thread completed")
                except Exception as e:
                    logger.error(f"Error in audio cleanup thread: {e}", exc_info=True)
                    logger.info("Attempting direct cleanup after thread failure...")
                    try:
                        self._cleanup_audio()
                        logger.info("Direct cleanup completed")
                    except Exception as e2:
                        logger.error(f"Error in direct cleanup: {e2}", exc_info=True)
            else:
                logger.info("No active audio resources to clean up")
            
            logger.info("Recording service stopped completely")
        except Exception as e:
            logger.error(f"Unexpected error in stop_recording: {e}", exc_info=True)
            raise  # Re-raise to ensure the error is properly handled upstream

    async def run_recorder(self):
        """Main recording loop using asyncio."""
        if self._stop_recording.is_set():
            return

        os.makedirs(WATCH_DIRECTORY, exist_ok=True)
        i = self.get_next_file_number(WATCH_DIRECTORY)
        
        logger.info("Starting recording service...")
        try:
            while not self._stop_recording.is_set():
                if self.recording:
                    await asyncio.sleep(0.01)
                    continue
                
                if self._stop_recording.is_set():
                    break
                    
                try:
                    file_name = os.path.join(WATCH_DIRECTORY, f'recording_{i}.wav')
                    await self.record_audio(file_name=file_name)
                    if self._stop_recording.is_set():
                        break
                    i += 1
                except Exception as e:
                    logger.error(f"Recording error in file {i}: {e}", exc_info=True)
                    if self._stop_recording.is_set():
                        break
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Recording loop interrupted with error: {e}", exc_info=True)
            # Don't re-raise, let the finally block handle cleanup
        finally:
            self._cleanup_audio()
            logger.info("Recording service stopped")

def main():
    """Standalone entry point for direct execution."""
    recorder = AudioRecorder()
    try:
        recorder.run_recorder()
    except KeyboardInterrupt:
        print("\nRecording stopped by user")
        recorder.stop_recording()
        sys.exit(0)

if __name__ == "__main__":
    main()
