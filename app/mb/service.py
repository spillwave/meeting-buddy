# service.py
import asyncio
import websockets
import json
import signal
import os
from datetime import datetime, timedelta

from websockets.protocol import State

from app import logger, ROOT_PATH, OUTPUT_DIRECTORY, WATCH_DIRECTORY, CONTEXT_DIRECTORY
from app.mb.record import AudioRecorder
from app.mb.prompt_manager import PromptManager
from app.mb.transcribe import Transcriber
from app.mb.config import Config
from app.mb.summarizer import run_summarizer
from litellm import completion
from app.mb.utils import rollover_directories, read_directory_files
import queue

class Service:
    def __init__(self):
        self.config = Config.load_config(os.path.join(ROOT_PATH, 'config.yaml'))
        self.recording = False
        self.output_queue = queue.Queue()
        self.clients = set()
        self.recorder = None
        self.transcriber = None
        self.transcription_task = None
        self.recorder_task = None
        self.summarize_lock = asyncio.Lock()  # Lock for summarization
        self.prompt_manager = PromptManager(self.config)
        self.prompts = self.prompt_manager.load_prompts()  # Explicitly load prompts
        self.started_at = datetime.now()
        
        # Verify prompts loaded correctly and contain required keys
        required_prompts = {'create_minute', 'create_ten_minute'}
        if not self.prompts:
            logger.error("No prompts were loaded")
            logger.error(f"Expected prompt files in: {self.prompt_manager.config.prompts_directory}")
            raise RuntimeError("No prompts were loaded")
            
        missing_prompts = required_prompts - set(self.prompts.keys())
        if missing_prompts:
            logger.error(f"Missing required prompts: {missing_prompts}")
            logger.error(f"Available prompts: {list(self.prompts.keys())}")
            logger.error(f"Prompt directory: {self.prompt_manager.prompt_directory}")
            raise RuntimeError(f"Required prompts not found: {missing_prompts}")
            
        logger.info(f"Successfully loaded prompts: {list(self.prompts.keys())}")


    def get_running_time_in_minutes(self) -> float:
        delta = (datetime.now() - self.started_at).total_seconds() / 60
        return int(delta)

    async def summarize_text(self, content: str, prompt: str=None) -> str:
        """Generate a summary of the provided text using LLM."""
        if not content.strip():
            logger.warning("Empty content provided to summarize_text")
            return ""

        if not prompt:
            minutes_elapsed = self.get_running_time_in_minutes()
            prompt_key = 'create_minute' if minutes_elapsed < 10 else 'create_ten_minute'
            prompt = self.prompt_manager.get_prompt(prompt_key)
            
            if not prompt:
                logger.error(f"Failed to get prompt template for key: {prompt_key}")
                logger.error(f"Available prompts: {list(self.prompt_manager.get_available_prompts())}")
                return f"Error: Missing prompt template for {prompt_key}"
            
        logger.debug(f"Using prompt template: {prompt[:100]}...")

        try:
            try:
                meeting_context = self.prompt_manager.load_meeting_context()
                logger.info(f"Loaded meeting context of length: {len(meeting_context)}")
            except Exception as e:
                logger.error(f"Error loading meeting context: {e}")
                meeting_context = ""
            
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"{meeting_context}\n\nTranscription:\n{content}"}
            ]
            
            logger.debug(f"Sending request to LLM with {len(messages)} messages")
            # Run the blocking LLM call in a thread
            response = await asyncio.to_thread(
                completion,
                model=self.config.local_llm_model,
                messages=messages,
                temperature=0.7,
                max_tokens=4000
            )
            
            if not response:
                logger.error("Received null response from LLM")
                return "Error: Null response from language model"
                
            if not hasattr(response, 'choices'):
                logger.error(f"Invalid response structure: {response}")
                return "Error: Invalid response structure from language model"
                
            if not response.choices:
                logger.error("Empty choices in LLM response")
                return "Error: No choices in language model response"
                
            summary = response.choices[0].message.content
            logger.info(f"Successfully generated summary of length: {len(summary)}")
            return summary
            
        except Exception as e:
            logger.error(f"Summarization error: {str(e)}", exc_info=True)
            return f"Error generating summary: {str(e)}"

    async def handler(self, websocket):
        client_failure = False
        self.clients.add(websocket)
        try:
            async for message in websocket:
                logger.info(f"Socket Message Received: {message}")
                command = json.loads(message)
                if command.get("action") == "start":
                    logger.info("Starting transcription service")
                    self.recording = True
                    # Send response before starting services
                    await websocket.send(json.dumps({"recording": True}))
                    # Start services after responding
                    await self.start_services()
                elif command.get("action") == "stop":
                    meeting_name = command.get("meeting_name", "")
                    logger.info(f"Stopping transcription service with meeting name: {meeting_name}")
                    # Send response before stopping services
                    await websocket.send(json.dumps({"recording": False}))
                    # Stop services after responding
                    try:
                        await self.stop_services(meeting_name, include_context=True)
                    except Exception as e:
                        logger.error(f"Error during stop_services: {e}", exc_info=True)
                        # Send error message to client
                        if websocket.state == State.OPEN:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "text": f"Error stopping services: {str(e)}"
                            }))
                elif command.get("action") == "summarize":
                    async with self.summarize_lock:
                        logger.info("Performing local LLM summarization")
                        text = command.get("text", "")
                        if not text.strip():
                            logger.warning("Received empty text for summarization")
                            await websocket.send(json.dumps({
                                "type": "error",
                                "text": "Cannot summarize empty text"
                            }))
                            continue
                            
                        try:
                            logger.debug(f"Attempting to summarize text of length: {len(text)}")
                            summary = await self.summarize_text(text)
                            if summary:
                                logger.info(f"Successfully generated summary of length: {len(summary)}")
                                try:
                                    if websocket.state == State.OPEN:
                                        await websocket.send(json.dumps({
                                            "type": "summary", 
                                            "text": summary
                                        }))
                                except Exception as ws_err:
                                    logger.error(f"Failed to send summary: {ws_err}")
                            else:
                                logger.error("Empty summary received from summarize_text")
                                try:
                                    if websocket.state == State.OPEN:
                                        await websocket.send(json.dumps({
                                            "type": "error",
                                            "text": "Failed to generate summary: empty response"
                                        }))
                                except Exception as ws_err:
                                    logger.error(f"Failed to send error message: {ws_err}")
                        except Exception as e:
                            error_msg = f"Error: Failed to generate summary - {str(e)}"
                            logger.error(f"Error in summarize handler: {str(e)}", exc_info=True)
                            try:
                                if not websocket.closed:
                                    await websocket.send(json.dumps({
                                        "type": "error",
                                        "text": error_msg
                                    }))
                            except Exception as ws_err:
                                logger.error(f"Failed to send error message: {ws_err}")
                elif command.get("action") == "download_files":
                    logger.info("Handling download_files request")
                    try:
                        # Get most recent transcription file
                        transcription_files = [f for f in os.listdir(OUTPUT_DIRECTORY) if f.endswith('transcription.txt')]
                        if transcription_files:
                            latest_transcription = max(transcription_files, key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIRECTORY, x)))
                            transcription_path = os.path.join(OUTPUT_DIRECTORY, latest_transcription)
                            if os.path.exists(transcription_path):
                                with open(transcription_path, 'rb') as f:
                                    transcription_data = f.read()
                                if websocket.state == State.OPEN:
                                    await websocket.send(json.dumps({
                                        "type": "file_data",
                                        "file_type": "transcription",
                                        "data": transcription_data.hex(),
                                        "filename": latest_transcription
                                    }))
                                logger.info("Sent transcription file data")
                            else:
                                logger.error(f"Transcription file not found: {transcription_path}")
                        else:
                            logger.error("No transcription files found")
                        
                        # Get most recent summary file from context directory
                        summary_file = os.path.join(CONTEXT_DIRECTORY, self.config.meeting_notes_file)
                        if os.path.exists(summary_file):
                            with open(summary_file, 'rb') as f:
                                summary_data = f.read()
                                try:
                                    if websocket.state == State.OPEN:
                                        await websocket.send(json.dumps({
                                            "type": "file_data",
                                            "file_type": "summary",
                                            "data": summary_data.hex(),
                                            "filename": self.config.meeting_notes_file
                                        }))
                                except Exception as ws_err:
                                    logger.error(f"Failed to send summary data: {ws_err}")
                    except Exception as e:
                        logger.error(f"Error handling download_files request: {e}")
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": f"Error retrieving files: {str(e)}"
                        }))
        except websockets.ConnectionClosed:
            logger.warning("Websocket connection closed!")
            client_failure = True
        except Exception as e:
            logger.error(f"Error in websocket handler: {e}")
            client_failure = True
        finally:
            if client_failure:
                self.clients.remove(websocket)
                logger.info("Client connection cleaned up")
                if len(self.clients) == 0:
                    logger.info("No active clients. Stopping services.")
                    await self.stop_services("unknown", include_context=True)

    async def start_services(self):
        # Check if output directory has content and rollover if needed
        if (
                (os.path.exists(OUTPUT_DIRECTORY) and any(os.listdir(OUTPUT_DIRECTORY))) or
                (os.path.exists(WATCH_DIRECTORY) and any(os.listdir(WATCH_DIRECTORY)))
        ):
            logger.info("Output directory not empty, probably due to a crash, rolling over files")
            rollover_directories("")

        # Initialize transcriber
        self.transcriber = Transcriber()

        # Create tasks for recorder and transcriber
        self.recorder_task = asyncio.create_task(self.run_recorder())
        self.transcription_task = asyncio.create_task(
            self.transcriber.run_transcriber(self.broadcast_transcription)
        )

    async def stop_services(self, meeting_name: str = "", include_context: bool = False):
        if self.recording:
            logger.info("Beginning stop_services process")
            self.recording = False
            
            # First stop the recorder and transcriber services
            if self.recorder:
                try:
                    logger.info("Stopping recorder...")
                    await self.recorder.stop_recording()
                    logger.info("Recorder stopped successfully")
                except Exception as e:
                    logger.error(f"Error stopping recorder: {e}", exc_info=True)
                    raise RuntimeError(f"Failed to stop recorder: {e}")
            
            if self.transcriber:
                try:
                    logger.info("Stopping transcriber...")
                    await self.transcriber.stop_transcriber()
                    logger.info("Transcriber stopped successfully")
                except Exception as e:
                    logger.error(f"Error stopping transcriber: {e}", exc_info=True)
                    raise RuntimeError(f"Failed to stop transcriber: {e}")

            # Then cancel their tasks with proper error handling
            if self.transcription_task:
                logger.info("Canceling transcription task...")
                self.transcription_task.cancel()
                try:
                    await self.transcription_task
                except asyncio.CancelledError:
                    logger.info("Transcription task cancelled successfully")
                except Exception as e:
                    logger.error(f"Error during transcription task cancellation: {e}", exc_info=True)
                    
            if self.recorder_task:
                logger.info("Canceling recorder task...")
                self.recorder_task.cancel()
                try:
                    await self.recorder_task
                except asyncio.CancelledError:
                    logger.info("Recorder task cancelled successfully")
                except Exception as e:
                    logger.error(f"Error during recorder task cancellation: {e}", exc_info=True)

            # Get transcription content from watch directory - only .txt files
            transcription_text = ""
            if os.path.exists(WATCH_DIRECTORY):
                # Get all .txt files and sort them (to maintain order)
                txt_files = sorted([f for f in os.listdir(WATCH_DIRECTORY) if f.endswith('.txt')])
                transcription_parts = []
                for txt_file in txt_files:
                    file_path = os.path.join(WATCH_DIRECTORY, txt_file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            if content:  # Only add non-empty content
                                transcription_parts.append(content)
                    except Exception as e:
                        logger.error(f"Error reading file {txt_file}: {e}")
                
                # Join all parts with line feeds
                transcription_text = '\n'.join(transcription_parts)

            if transcription_text:
                try:
                    # Generate final summary using create_meeting_notes with timeout protection
                    from mb.create_meeting_notes import run_summarizer
                    logger.info("Starting final summary generation...")
                    
                    try:
                        # Allow up to 3 minutes for summarization
                        final_summary = await asyncio.wait_for(
                            asyncio.to_thread(
                                run_summarizer,
                                transcription_text,
                                self.config,
                                service=self,
                                prompt_manager=self.prompt_manager
                            ),
                            timeout=180.0
                        )
                        
                        if not final_summary:
                            raise RuntimeError("Final summary generation returned empty result")
                            
                        if final_summary.startswith("Error"):
                            raise RuntimeError(final_summary)
                            
                        logger.info("Final summary generated successfully")
                        data = {"type": "final_summary", "text": final_summary}
                        message = json.dumps(data)
                        
                        # Keep trying to send summary for up to 30 seconds
                        send_attempts = 3
                        while send_attempts > 0:
                            active_clients = [
                                client for client in self.clients
                                if client.state == State.OPEN
                            ]
                            if active_clients:
                                try:
                                    tasks = []
                                    for client in active_clients:
                                        try:
                                            tasks.append(asyncio.create_task(client.send(message)))
                                        except Exception as client_err:
                                            logger.error(f"Error creating send task for client: {client_err}")
                                            continue
                                            
                                    if tasks:
                                        await asyncio.wait_for(
                                            asyncio.gather(*tasks, return_exceptions=True),
                                            timeout=10.0
                                        )
                                        break  # Successfully sent to clients
                                    else:
                                        logger.error("No valid clients to send summary to")
                                        break
                                except asyncio.TimeoutError:
                                    logger.warning(f"Timeout sending summary, attempts left: {send_attempts}")
                                    send_attempts -= 1
                                except Exception as e:
                                    logger.error(f"Error sending summary: {e}", exc_info=True)
                                    send_attempts -= 1
                            else:
                                logger.warning("No active clients to send summary to")
                                break
                                
                    except asyncio.TimeoutError:
                        error_msg = "Error: Timeout while generating final summary"
                        logger.error(error_msg)
                        await self.broadcast_error(error_msg)
                    except Exception as e:
                        error_msg = f"Error: Failed to generate final summary - {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        await self.broadcast_error(error_msg)
                        
                except Exception as outer_e:
                    logger.error(f"Critical error in summary generation: {outer_e}", exc_info=True)
                    await self.broadcast_error(f"Critical error in summary generation: {str(outer_e)}")
            
            # Now roll over directories with sanitized meeting name
            meeting_name = meeting_name.strip() if meeting_name else "Untitled_Meeting"
            # Ensure meeting name is properly sanitized and non-empty
            safe_meeting_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in meeting_name)
            if not safe_meeting_name:
                safe_meeting_name = "Untitled_Meeting"
            logger.info(f"Rolling over directories with meeting name: {safe_meeting_name}")
            rollover_directories(safe_meeting_name, include_context)


    async def run_recorder(self):
        self.recorder = AudioRecorder()
        await self.recorder.run_recorder()

    async def broadcast_transcription(self, text: str):
        """Broadcast transcription to all connected clients."""
        if text:
            data = {"type": "transcription", "text": text}
            message = json.dumps(data)
            # Filter out closed connections first
            active_clients = [client for client in self.clients if client.state != State.CLOSED]
            if active_clients:
                try:
                    # Create tasks for each send operation
                    tasks = [asyncio.create_task(client.send(message)) for client in active_clients]
                    logger.info(f"Writing message to active clients: {message}")
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    logger.error(f"Error broadcasting to clients: {e}")
            else:
                logger.warning("No active clients")

    async def broadcast_error(self, error: str):
        """Broadcast error message to all connected clients."""
        data = {"type": "error", "text": error}
        message = json.dumps(data)
        # Filter out closed connections first
        active_clients = [client for client in self.clients if client.state != State.CLOSED]
        if active_clients:
            try:
                # Create tasks for each send operation
                tasks = [asyncio.create_task(client.send(message)) for client in active_clients]
                logger.info(f"Writing error message to active clients: {message}")
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error broadcasting error to clients: {e}")
        else:
            logger.warning("No active clients")

    async def main(self, set_signal_handlers=True):
        loop = asyncio.get_running_loop()
        self.stop = loop.create_future()  # Create Future in the running loop
        if set_signal_handlers:
            for s in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    s, lambda s=s: asyncio.create_task(self.shutdown(s))
                )

        server = await websockets.serve(self.handler, "localhost", self.config.websocket_port)
        logger.info(f"Websocket server started on ws://localhost:{self.config.websocket_port}")
        try:
            await self.stop  # Wait until shutdown signal
        finally:
            server.close()
            await server.wait_closed()
            # Ensure all clients are closed
            for client in self.clients:
                if not client.closed:
                    await client.close()
            logger.info("Websocket server closed.")

    async def shutdown(self, sig):
        """Cleanup tasks tied to the service's shutdown."""
        import signal as signals_module  # Import inside function to avoid confusion
        signal_name = signals_module.Signals(sig).name
        logger.info(f"Received exit signal {signal_name}...")
        self.stop.set_result(None)
        # Cancel all tasks excluding the current one
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        logger.info(f"Cancelling {len(tasks)} outstanding tasks")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

def main():
    service = Service()
    try:
        asyncio.run(service.main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Exiting...")
    finally:
        logger.info("Successfully shutdown the service.")

if __name__ == "__main__":
    main()
