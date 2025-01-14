import asyncio
import json
import logging
import time
import websockets
from websockets.protocol import State

logger = logging.getLogger(__name__)

async def websocket_client(in_message_queue, out_message_queue, config):
    """Handle WebSocket client connection and message processing."""
    ws_url = f"ws://localhost:{config.websocket_port}"
    try:
        async with websockets.connect(ws_url) as websocket:
            await websocket.send(json.dumps({"action": "start"}))
            out_message_queue.put(("state_update", {"transcribing": True}))

            last_summary_time = time.time()
            current_text = ""
            waiting_for_final_summary = False
            stop_requested = False
            received_final_summary = False
            expected_file_types = {"transcription": False, "summary": False}

            async def stopping(meeting_name):
                nonlocal waiting_for_final_summary, stop_requested
                logger.info(f"Stop message received with meeting name: {meeting_name}")
                await websocket.send(json.dumps({
                    "action": "stop",
                    "meeting_name": meeting_name
                }))
                await websocket.send(json.dumps({
                    "action": "download_files"
                }))
                logger.info("Requested file contents for download after stop")
                waiting_for_final_summary = True
                stop_requested = True
                logger.info("Waiting for final summary and files before closing connection...")

            while True:
                try:
                    timeout = 60 if (waiting_for_final_summary or stop_requested) else 1
                    data = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                    message = json.loads(data)

                    logger.debug(f"Message over socket-in-thread-to-queue: {message}")
                    
                    if message.get("type") == "transcription":
                        text = message.get("text", "")
                        current_text += text + '\n'
                        out_message_queue.put(("transcription", text))
                        logger.info(f"Put transcription on queue: {text}")

                        current_time = time.time()
                        if current_time - last_summary_time >= config.summary_interval:
                            await websocket.send(json.dumps({
                                "action": "summarize",
                                "text": current_text
                            }))
                            last_summary_time = current_time

                    elif message.get("type") == "summary":
                        summary = message.get("text", "")
                        out_message_queue.put(("summary", summary))
                        logger.info(f"Put summary on queue: {summary}")

                    elif message.get("type") == "final_summary":
                        final_summary = message.get("text", "")
                        out_message_queue.put(("final_summary", final_summary))
                        logger.info("Received final summary")
                        received_final_summary = True

                    elif message.get("type") == "error":
                        error_text = message.get("text", "Unknown error")
                        logger.error(f"Received error from server: {error_text}")
                        out_message_queue.put(("error", error_text))
                        if waiting_for_final_summary:
                            out_message_queue.put(("state_update", {"transcribing": False}))
                            out_message_queue.put(("stopped", None))
                            break

                    elif message.get("type") == "file_data":
                        file_type = message.get("file_type")
                        data = bytes.fromhex(message.get("data", ""))
                        filename = message.get("filename", "")
                        out_message_queue.put(("file_data", {
                            "type": file_type,
                            "data": data,
                            "filename": filename
                        }))
                        logger.info(f"Received {file_type} file data for download")
                        
                        expected_file_types[file_type] = True
                        
                        if all(expected_file_types.values()) and stop_requested:
                            logger.info("All expected files received, closing connection")
                            out_message_queue.put(("state_update", {"transcribing": False}))
                            out_message_queue.put(("stopped", None))
                            break

                    while not in_message_queue.empty():
                        cmd_type, payload = in_message_queue.get_nowait()
                        if cmd_type == "stop":
                            await stopping(payload)
                        elif cmd_type == "download_files":
                            await websocket.send(json.dumps({
                                "action": "download_files"
                            }))
                            logger.info("Requested file contents for download")

                    if received_final_summary and all(expected_file_types.values()):
                        logger.info("Received final summary and all expected files, closing connection")
                        out_message_queue.put(("state_update", {"transcribing": False}))
                        out_message_queue.put(("stopped", None))
                        break

                except asyncio.TimeoutError:
                    if waiting_for_final_summary:
                        logger.warning("Timeout while waiting for final summary")
                        if stop_requested:
                            logger.error("Timed out waiting for final summary, closing connection")
                            out_message_queue.put(("error", "Timed out waiting for final summary"))
                            out_message_queue.put(("state_update", {"transcribing": False}))
                            out_message_queue.put(("stopped", None))
                            break
                    continue
                except websockets.ConnectionClosed:
                    logger.warning("Websocket connection closed")
                    if not waiting_for_final_summary:
                        logger.error("Unexpected connection closure")
                        out_message_queue.put(("error", "Connection closed unexpectedly"))
                    out_message_queue.put(("state_update", {"transcribing": False}))
                    out_message_queue.put(("stopped", None))
                    break
    except Exception as e:
        logger.error(f"Error in websocket client: {str(e)}", exc_info=True)
        out_message_queue.put(("error", f"Connection error: {str(e)}"))
        out_message_queue.put(("state_update", {"transcribing": False}))
        out_message_queue.put(("stopped", None))

def websocket_client_thread(in_message_queue, out_message_queue, config):
    """Run the WebSocket client in a separate thread."""
    asyncio.run(websocket_client(in_message_queue, out_message_queue, config))
