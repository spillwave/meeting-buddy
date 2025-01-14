import asyncio
import pytest_asyncio
import pytest
import json
import websockets
from unittest.mock import patch, MagicMock, AsyncMock
import pyaudio
from app.mb.service import Service
from app.mb.config import Config

class MockLLMResponse:
    def __init__(self, content):
        self.choices = [MagicMock(message=MagicMock(content=content))]

# Mock PyAudio and AudioRecorder
@pytest.fixture(autouse=True)
def mock_audio_resources():
    with patch('pyaudio.PyAudio') as mock_pyaudio, \
         patch('app.mb.record.AudioRecorder') as mock_recorder, \
         patch('app.mb.transcribe.Transcriber') as mock_transcriber, \
         patch('litellm.completion') as mock_completion:
        
        # Setup mock audio stream
        mock_stream = MagicMock()
        mock_stream.read.return_value = b'dummy audio data'
        mock_pyaudio.return_value.open.return_value = mock_stream
        
        # Setup mock recorder
        mock_recorder_instance = MagicMock()
        mock_recorder_instance.record_audio = AsyncMock()
        mock_recorder_instance.stop_recording = AsyncMock()
        mock_recorder.return_value = mock_recorder_instance
        
        # Setup mock transcriber
        mock_transcriber_instance = MagicMock()
        mock_transcriber_instance.run_transcriber = AsyncMock()
        mock_transcriber_instance.stop_transcriber = AsyncMock()
        mock_transcriber.return_value = mock_transcriber_instance
        
        # Setup mock LLM completion
        def mock_llm(*args, **kwargs):
            return MockLLMResponse("Test summary response")
        mock_completion.side_effect = mock_llm
        
        yield

@pytest_asyncio.fixture(scope="function")
async def service():
    """Fixture that starts the websocket service"""
    svc = Service()
    server_task = asyncio.create_task(svc.main(set_signal_handlers=False))
    
    # Add initial delay to allow server to start
    await asyncio.sleep(0.5)
    
    # Wait for server to start
    config = Config.load_config()
    ws_url = f'ws://localhost:{config.websocket_port}'
    
    for attempt in range(10):  # Try for up to 2 seconds
        try:
            async with websockets.connect(ws_url, open_timeout=5) as ws:
                break
        except (ConnectionRefusedError, websockets.exceptions.WebSocketException) as e:
            print(f"Connection attempt {attempt + 1} failed: {str(e)}")
            await asyncio.sleep(0.2)
    else:
        raise RuntimeError("Failed to connect to websocket server after 10 attempts")

    yield svc
    
    # Cleanup
    await svc.shutdown(15)  # SIGTERM
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass  # Expected during cleanup

@pytest.mark.asyncio
async def test_handler_start_command(service):
    """Test handling of 'start' command"""
    config = Config.load_config()
    ws_url = f'ws://localhost:{config.websocket_port}'
    
    try:
        async with websockets.connect(ws_url) as ws:
            # Send start command with timeout
            command = json.dumps({'action': 'start'})
            print(f"Sending command: {command}")
            await asyncio.wait_for(ws.send(command), timeout=5)
            
            # Wait for response with timeout
            print("Waiting for response...")
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"Received response: {response}")
            
            response_data = json.loads(response)
            assert response_data.get('recording') is True
    except asyncio.TimeoutError as e:
        print("Timeout occurred while waiting for response")
        raise
    except Exception as e:
        print(f"Error during test: {str(e)}")
        raise

@pytest.mark.asyncio
async def test_handler_stop_command(service):
    """Test handling of 'stop' command"""
    config = Config.load_config()
    ws_url = f'ws://localhost:{config.websocket_port}'
    
    try:
        async with websockets.connect(ws_url) as ws:
            # Send stop command with timeout
            command = json.dumps({
                'action': 'stop',
                'meeting_name': 'test_meeting'
            })
            print(f"Sending command: {command}")
            await asyncio.wait_for(ws.send(command), timeout=5)
            
            # Wait for response with timeout
            print("Waiting for response...")
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"Received response: {response}")
            
            response_data = json.loads(response)
            assert response_data.get('recording') is False
    except asyncio.TimeoutError as e:
        print("Timeout occurred while waiting for response")
        raise
    except Exception as e:
        print(f"Error during test: {str(e)}")
        raise

@pytest.mark.asyncio
async def test_handler_summarize_command(service):
    """Test handling of 'summarize' command"""
    test_text = "This is a test text that needs to be summarized."
    config = Config.load_config()
    ws_url = f'ws://localhost:{config.websocket_port}'
    
    try:
        async with websockets.connect(ws_url) as ws:
            # Send summarize command with timeout
            command = json.dumps({
                'action': 'summarize',
                'text': test_text
            })
            print(f"Sending command: {command}")
            await asyncio.wait_for(ws.send(command), timeout=5)
            
            # Wait for response with timeout
            print("Waiting for response...")
            response = await asyncio.wait_for(ws.recv(), timeout=10)  # Increased timeout
            print(f"Received response: {response}")
            
            response_data = json.loads(response)
            assert response_data.get('type') == 'summary'
            assert isinstance(response_data.get('text'), str)
            assert len(response_data.get('text')) > 0
    except asyncio.TimeoutError as e:
        print("Timeout occurred while waiting for response")
        raise
    except Exception as e:
        print(f"Error during test: {str(e)}")
        raise

@pytest.mark.skip(reason="Multiple client test needs to be redesigned")
@pytest.mark.asyncio
async def test_multiple_clients(service):
    """Test interaction between multiple clients"""
    config = Config.load_config()
    ws_url = f'ws://localhost:{config.websocket_port}'
    
    async def client_1():
        try:
            async with websockets.connect(ws_url) as ws:
                # Send start command with timeout
                command = json.dumps({'action': 'start'})
                print(f"Sending command: {command}")
                await asyncio.wait_for(ws.send(command), timeout=5)
                
                # Wait for response with timeout
                print("Waiting for response...")
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                print(f"Received response: {response}")
                
                response_data = json.loads(response)
                assert response_data.get('recording') is True
        except asyncio.TimeoutError as e:
            print("Timeout occurred while waiting for response")
            raise
        except Exception as e:
            print(f"Error during test: {str(e)}")
            raise

    async def client_2():
        try:
            await asyncio.sleep(1)  # Wait for client 1 to connect
            async with websockets.connect(ws_url) as ws:
                # Wait for response with timeout
                print("Waiting for response...")
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                print(f"Received response: {response}")
                
                response_data = json.loads(response)
                assert response_data.get('recording') is True
        except asyncio.TimeoutError as e:
            print("Timeout occurred while waiting for response")
            raise
        except Exception as e:
            print(f"Error during test: {str(e)}")
            raise

    await asyncio.gather(client_1(), client_2())
