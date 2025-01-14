import os
import time
import re
import sys
import traceback

import torch
import asyncio
import aiofiles
from datetime import datetime
import whisper
from tqdm import tqdm

from app import logger, WATCH_DIRECTORY

# Set environment variables to limit threading and multiprocessing
os.environ["FFMPEG_BINARY"] = "/opt/homebrew/bin/ffmpeg"  # Explicitly set ffmpeg path
os.environ["PATH"] = f"/opt/homebrew/bin:{os.environ.get('PATH', '')}"  # Add Homebrew bin to PATH
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# Limit torch threads
torch.set_num_threads(1)
# torch.set_num_interop_threads(1)


class Transcriber:
    """Handles audio transcription functionality."""

    def __init__(self):
        self.processed_files = set()
        self.model = None
        self._load_model()
        self.running = False

    def _load_model(self):
        """Load the Whisper model."""
        try:
            if self.model is not None:
                del self.model
                self.model = None
                # Force garbage collection to clean up CUDA memory
                import gc
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            self.model = whisper.load_model("base")
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self.model = None

    @staticmethod
    def extract_number(file_name):
        """Extract the number from the filename like 'recording_1.wav'."""
        match = re.search(r'(\d+)', file_name)
        return int(match.group(1)) if match else float('inf')

    def get_unprocessed_wav_files(self):
        """Return a list of unprocessed wav files in the directory, sorted by number."""
        if not os.path.exists(WATCH_DIRECTORY):
            print(f"Directory {WATCH_DIRECTORY} does not exist.")
            return []

        wav_files = [f for f in os.listdir(WATCH_DIRECTORY) if f.endswith('.wav')]
        unprocessed_files = []
        for wav_file in wav_files:
            txt_file = wav_file.replace('.wav', '.txt')
            if txt_file not in self.processed_files and not os.path.exists(os.path.join(WATCH_DIRECTORY, txt_file)):
                unprocessed_files.append(wav_file)

        # Sort files based on the number in the filename
        return sorted(unprocessed_files, key=self.extract_number)

    async def process_file(self, file):
        """Process the .wav file using whisper and mark it as processed."""
        if self.model is None:
            logger.error("Whisper model not loaded, attempting to reload...")
            self._load_model()
            if self.model is None:
                logger.error("Failed to reload model, skipping transcription")
                return

        file_path = os.path.join(WATCH_DIRECTORY, file)
        output_path = os.path.join(WATCH_DIRECTORY, file.replace('.wav', '.txt'))

        try:
            start_time = datetime.now()
            logger.info(f"Starting transcription of {file_path}")

            # Run the CPU-intensive transcription in a thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.model.transcribe(
                    file_path, 
                    fp16=False, 
                    language="English", 
                    no_speech_threshold=0.8,
                    logprob_threshold=-1.0,
                    compression_ratio_threshold=2.4
                )
            )

            # Write the transcription to a text file
            async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                await f.write(result["text"])

            duration = datetime.now() - start_time
            logger.info(f"Completed transcription of {file} in {duration.total_seconds():.1f} seconds")
            self.processed_files.add(file.replace('.wav', '.txt'))
            return result["text"]
        except Exception as e:
            traceback.print_exc()
            if "No such file or directory: 'ffmpeg'" in str(e):
                logger.error(f"Failed to locate ffmpeg, which is required. Please install ffmpeg. `brew install ffmpeg`. If you have installed it, ensure your watch directory is a valid location.")
            else:
                logger.error(f"Error processing {file}: {e}")
            return None

    async def run_transcriber(self, callback):
        """Main transcription loop using async/await."""
        logger.info("Starting transcription service")
        self.running = True
        
        while self.running:
            try:
                unprocessed_files = self.get_unprocessed_wav_files()
                if unprocessed_files:
                    logger.info(f"Found {len(unprocessed_files)} new files to process")
                    for file in tqdm(unprocessed_files):
                        if not self.running:
                            break
                        text = await self.process_file(file)
                        if text:
                            await callback(text)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Transcription error: {e}")
                await asyncio.sleep(1)

        logger.info("Transcription service stopped")

    async def stop_transcriber(self):
        """Stop the transcription process cleanly."""
        self.running = False
        logger.info("Transcription service stopping...")
        # Clean up Whisper model resources
        if self.model:
            del self.model
            self.model = None
            # Force garbage collection
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


def main():
    """Standalone entry point for direct execution."""
    transcriber = Transcriber()
    try:
        asyncio.run(transcriber.run_transcriber(print))
    except KeyboardInterrupt:
        transcriber.stop_transcriber()
        logger.info("Transcription service stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
