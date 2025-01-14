#!/usr/bin/env python3
import asyncio
import websockets
import json
import argparse
import sys
from typing import Optional
from app.mb.config import Config

class WebSocketTestClient:
    def __init__(self, uri: str = None):
        config = Config()
        self.uri = uri or f"ws://localhost:{config.websocket_port}"
        self.websocket = None
        self._recv_lock = asyncio.Lock()
        self._stop_listening = asyncio.Event()

    async def _send_and_receive(self, message):
        """Send a message and wait for response with proper locking."""
        async with self._recv_lock:
            await self.websocket.send(json.dumps(message))
            return await self.websocket.recv()

    async def connect(self):
        """Connect to the websocket server."""
        try:
            self.websocket = await websockets.connect(self.uri)
            print(f"Connected to {self.uri}")
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    async def start_recording(self):
        """Send start recording command."""
        message = {"action": "start"}
        response = await self._send_and_receive(message)
        print(f"Response: {response}")

    async def stop_recording(self, meeting_name: Optional[str] = None):
        """Send stop recording command."""
        message = {"action": "stop"}
        if meeting_name:
            message["meeting_name"] = meeting_name
        response = await self._send_and_receive(message)
        print(f"Response: {response}")

    async def request_summary(self, text: str):
        """Request a summary of provided text."""
        message = {
            "action": "summarize",
            "text": text
        }
        response = await self._send_and_receive(message)
        print(f"Response: {response}")

    async def stop_listening(self):
        """Stop listening for messages."""
        self._stop_listening.set()

    async def listen_for_messages(self):
        """Listen for incoming messages from the server."""
        self._stop_listening.clear()
        async with self._recv_lock:
            while not self._stop_listening.is_set():
                try:
                    # Use wait_for to make the recv operation cancellable
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=0.1)
                    print(f"Received: {message}")
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break
                except Exception as e:
                    print(f"Error receiving message: {e}")
                    break

async def handle_command(client: WebSocketTestClient, command: str, meeting_name: str = None, text: str = None):
    """Handle execution of a specific command."""
    if command == "start":
        await client.start_recording()
    elif command == "stop":
        await client.stop_recording(meeting_name)
    elif command == "summarize":
        if not text:
            print("Error: Text required for summarize command")
            return
        await client.request_summary(text)
    elif command == "listen":
        await client.listen_for_messages()
    elif command == "stoplisten":
        await client.stop_listening()

async def interactive_loop(client: WebSocketTestClient):
    """Run an interactive loop for command execution."""
    print("\nAvailable commands:")
    print("  start - Start recording")
    print("  stop [meeting_name] - Stop recording")
    print("  summarize <text> - Request summary of text")
    print("  listen - Listen for messages")
    print("  stoplisten - Stop listening for messages")
    print("  quit - Exit the program")
    print("\nEnter commands (type 'quit' to exit):")

    while True:
        try:
            command_line = await asyncio.get_event_loop().run_in_executor(
                None, input, "\nEnter command> "
            )
            
            if command_line.lower() == 'quit':
                break

            parts = command_line.split(maxsplit=2)
            if not parts:
                continue
                
            command = parts[0].lower()
            
            if command == "stop" and len(parts) > 1:
                await client.stop_recording(parts[1])
            elif command == "summarize" and len(parts) > 1:
                await client.request_summary(parts[1])
            elif command == "start":
                await client.start_recording()
            elif command == "listen":
                asyncio.create_task(client.listen_for_messages())
            elif command == "stoplisten":
                await client.stop_listening()
            else:
                print("Invalid command or missing arguments")
                continue

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error: {e}")

async def main():
    parser = argparse.ArgumentParser(description='WebSocket Test Client')
    parser.add_argument('--uri', default=None, help='WebSocket URI')

    args = parser.parse_args()
    
    client = WebSocketTestClient(args.uri)
    if not await client.connect():
        sys.exit(1)

    try:
        await interactive_loop(client)
    finally:
        if client.websocket:
            await client.websocket.close()

if __name__ == "__main__":
    asyncio.run(main())
