import pytest
import asyncio
from unittest import mock
from queue import Queue
from app.mb.websocket_client import websocket_client

@pytest.fixture
def mock_config():
    class MockConfig:
        websocket_port = 9999
    return MockConfig()

@pytest.fixture
def in_message_queue():
    return Queue()

@pytest.fixture
def out_message_queue():
    return Queue()

@pytest.mark.asyncio
async def test_websocket_client_connection(in_message_queue, out_message_queue, mock_config):
    # Mock the websockets.connect to prevent actual network calls
    with mock.patch('websockets.connect', new_callable=mock.AsyncMock) as mock_connect:
        mock_ws = mock.AsyncMock()
        mock_connect.return_value = mock_ws

        # Run the websocket_client in an asyncio task
        client_task = asyncio.create_task(
            websocket_client(in_message_queue, out_message_queue, mock_config)
        )

        # Allow the client to run a bit and then cancel
        await asyncio.sleep(0.1)
        client_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await client_task

        # Check that the client attempted to connect
        mock_connect.assert_called_with(f"ws://localhost:{mock_config.websocket_port}")

@pytest.mark.asyncio
async def test_websocket_client_start_command(in_message_queue, out_message_queue, mock_config):
    with mock.patch('websockets.connect', new_callable=mock.AsyncMock) as mock_connect:
        mock_ws = mock.AsyncMock()
        mock_connect.return_value = mock_ws
        
        # Set up the mock websocket to return a response
        mock_ws.recv.side_effect = [
            '{"recording": true}',
            asyncio.CancelledError  # To end the loop
        ]
        
        client_task = asyncio.create_task(
            websocket_client(in_message_queue, out_message_queue, mock_config)
        )
        
        await asyncio.sleep(0.1)
        client_task.cancel()
        
        # Verify start command was sent
        mock_ws.send.assert_called_with('{"action": "start"}')
