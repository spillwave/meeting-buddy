import asyncio
import json
import logging
import time
import websockets
from websockets.protocol import State

logger = logging.getLogger(__name__)

class WebSocketClient:
    """WebSocket client with automatic reconnection and state management."""
    def __init__(self, in_message_queue, out_message_queue, config):
        self.in_message_queue = in_message_queue
        self.out_message_queue = out_message_queue
        self.config = config
        self.ws_url = f"ws://localhost:{config.websocket_port}"
        self.websocket = None
        self.connected = False
        self.should_reconnect = True
        self.reconnect_interval = 1  # Start with 1 second
        self.max_reconnect_interval = 30  # Max 30 seconds between attempts
        self.last_message_time = 0
        self.heartbeat_interval = 30  # Send heartbeat every 30 seconds

    async def connect(self):
        """Establish WebSocket connection with automatic reconnection."""
        while self.should_reconnect:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    self.websocket = websocket
                    self.connected = True
                    self.reconnect_interval = 1  # Reset reconnect interval on successful connection
                    self.last_message_time = time.time()
                    
                    # Start heartbeat task
                    heartbeat_task = asyncio.create_task(self.send_heartbeat())
                    
                    # Restore previous state if needed
                    if hasattr(self, 'current_text'):
                        await self.send_message({"action": "start"})
                        self.out_message_queue.put(("state_update", {"transcribing": True}))
                    
                    await self.message_loop()
                    
                    # Cancel heartbeat when connection closes
                    heartbeat_task.cancel()
                    
            except (websockets.exceptions.ConnectionClosed, 
                    websockets.exceptions.WebSocketException,
                    ConnectionRefusedError) as e:
                logger.warning(f"WebSocket connection failed: {str(e)}")
                self.connected = False
                self.websocket = None
                
                if self.should_reconnect:
                    logger.info(f"Attempting to reconnect in {self.reconnect_interval} seconds...")
                    await asyncio.sleep(self.reconnect_interval)
                    # Exponential backoff with max limit
                    self.reconnect_interval = min(self.reconnect_interval * 2, self.max_reconnect_interval)
                    continue
                break

    async def send_heartbeat(self):
        """Send periodic heartbeat to keep connection alive."""
        while self.connected:
            try:
                if time.time() - self.last_message_time > self.heartbeat_interval:
                    await self.send_message({"action": "heartbeat"})
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.warning(f"Failed to send heartbeat: {str(e)}")

    async def send_message(self, message):
        """Send message with retry logic."""
        if not self.connected:
            logger.warning("Cannot send message: not connected")
            return False
            
        try:
            await self.websocket.send(json.dumps(message))
            self.last_message_time = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            self.connected = False
            return False

    async def message_loop(self):
        """Main message processing loop."""
        self.current_text = ""
        self.waiting_for_final_summary = False
        self.stop_requested = False
        self.received_final_summary = False
        self.expected_file_types = {"transcription": False, "summary": False}
        last_summary_time = time.time()

        while self.connected:
            try:
                # Handle incoming websocket messages
                timeout = 60 if (self.waiting_for_final_summary or self.stop_requested) else 1
                data = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
                message = json.loads(data)
                self.last_message_time = time.time()

                await self.process_message(message, last_summary_time)

                # Handle outgoing messages from queue
                while not self.in_message_queue.empty():
                    msg_type, msg_data = self.in_message_queue.get_nowait()
                    if msg_type == "stop":
                        await self.handle_stop(msg_data)
                    # Add other message type handlers as needed

            except asyncio.TimeoutError:
                if self.waiting_for_final_summary:
                    logger.warning("Timeout waiting for final summary")
                    self.out_message_queue.put(("error", "Timeout waiting for final summary"))
                    break
                continue
            except Exception as e:
                logger.error(f"Error in message loop: {str(e)}")
                break

    async def process_message(self, message, last_summary_time):
        """Process incoming websocket messages."""
        msg_type = message.get("type")
        
        if msg_type == "transcription":
            text = message.get("text", "")
            self.current_text += text + '\n'
            self.out_message_queue.put(("transcription", text))
            
            current_time = time.time()
            if current_time - last_summary_time >= self.config.summary_interval:
                await self.send_message({
                    "action": "summarize",
                    "text": self.current_text
                })
                last_summary_time = current_time

        elif msg_type == "summary":
            summary = message.get("text", "")
            self.out_message_queue.put(("summary", summary))

        elif msg_type == "final_summary":
            final_summary = message.get("text", "")
            self.out_message_queue.put(("final_summary", final_summary))
            self.received_final_summary = True

        elif msg_type == "error":
            error_text = message.get("text", "Unknown error")
            self.out_message_queue.put(("error", error_text))
            if self.waiting_for_final_summary:
                self.out_message_queue.put(("state_update", {"transcribing": False}))
                self.out_message_queue.put(("stopped", None))

        elif msg_type == "file_data":
            await self.handle_file_data(message)

    async def handle_stop(self, meeting_name):
        """Handle stop request."""
        logger.info(f"Stop message received with meeting name: {meeting_name}")
        await self.send_message({
            "action": "stop",
            "meeting_name": meeting_name
        })
        await self.send_message({
            "action": "download_files"
        })
        logger.info("Requested file contents for download after stop")
        self.waiting_for_final_summary = True
        self.stop_requested = True

    async def handle_file_data(self, message):
        """Handle incoming file data."""
        file_type = message.get("file_type")
        data = bytes.fromhex(message.get("data", ""))
        filename = message.get("filename", "")
        
        self.out_message_queue.put(("file_data", {
            "type": file_type,
            "data": data,
            "filename": filename
        }))
        
        self.expected_file_types[file_type] = True
        
        if all(self.expected_file_types.values()) and self.stop_requested:
            logger.info("All expected files received, closing connection")
            self.out_message_queue.put(("state_update", {"transcribing": False}))
            self.out_message_queue.put(("stopped", None))
            self.should_reconnect = False

async def websocket_client(in_message_queue, out_message_queue, config):
    """Handle WebSocket client connection and message processing."""
    client = WebSocketClient(in_message_queue, out_message_queue, config)
    await client.connect()

def websocket_client_thread(in_message_queue, out_message_queue, config):
    """Run the WebSocket client in a separate thread."""
    asyncio.run(websocket_client(in_message_queue, out_message_queue, config))
