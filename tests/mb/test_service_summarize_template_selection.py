import pytest
import json
import websockets
from websockets.frames import Close
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from app.mb.service import Service
from app.mb.prompt_manager import PromptManager

@pytest.fixture
def service():
    return Service()

@pytest.mark.asyncio
async def test_prompt_selection_based_on_time():
    """Test that the correct prompt is selected based on elapsed time"""
    service = Service()
    
    # Mock the prompts
    service.prompts = {
        'create_minute': 'minute prompt',
        'create_ten_minute': 'ten minute prompt'
    }
    
    # Mock datetime.now() to return our fixed test time
    fixed_time = datetime(2024, 12, 30, 21, 5, 48)  # Using provided time
    
    # Test case 1: Less than 10 minutes elapsed
    with patch('app.mb.service.datetime') as mock_datetime:
        mock_datetime.now.return_value = fixed_time + timedelta(minutes=5)
        # Set the started_at time 5 minutes before our fixed time
        service.started_at = fixed_time
        
        # Mock completion to avoid actual LLM calls
        with patch('app.mb.service.completion') as mock_completion:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Test summary"
            mock_completion.return_value = mock_response
            
            # Mock prompt_manager.load_meeting_context
            with patch.object(PromptManager, 'load_meeting_context', return_value=""):
                await service.summarize_text("test content")
                
                # Verify the minute prompt was used
                assert mock_completion.call_args[1]['messages'][0]['content'] == 'minute prompt'

    # Test case 2: More than 10 minutes elapsed
    with patch('app.mb.service.datetime') as mock_datetime:
        mock_datetime.now.return_value = fixed_time + timedelta(minutes=15)
        # Set the started_at time 15 minutes before our fixed time
        service.started_at = fixed_time
        
        # Mock completion to avoid actual LLM calls
        with patch('app.mb.service.completion') as mock_completion:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Test summary"
            mock_completion.return_value = mock_response
            
            # Mock prompt_manager.load_meeting_context
            with patch.object(PromptManager, 'load_meeting_context', return_value=""):
                await service.summarize_text("test content")
                
                # Verify the ten minute prompt was used
                assert mock_completion.call_args[1]['messages'][0]['content'] == 'ten minute prompt'
