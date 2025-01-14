import pytest
from unittest.mock import MagicMock, patch
from queue import Queue
from app.mb.message_processor import MessageProcessor

@pytest.fixture
def in_queue():
    return Queue()

@pytest.fixture
def out_queue():
    return Queue()

def test_process_transcription_message(out_queue, in_queue):
    # Mock Streamlit session state
    with patch('streamlit.session_state') as mock_session_state:
        mock_session_state.transcription_text = ""
        mock_session_state.first_transcription_received = False

        processor = MessageProcessor(in_queue, out_queue)
        out_queue.put(('transcription', 'Test transcription'))

        processor.process_messages()

        assert mock_session_state.transcription_text == 'Test transcription\n'
        assert mock_session_state.first_transcription_received == True

def test_process_summary_message(out_queue, in_queue):
    with patch('streamlit.session_state') as mock_session_state:
        mock_session_state.interim_summary_text = ""

        processor = MessageProcessor(in_queue, out_queue)
        out_queue.put(('summary', 'Test summary'))

        processor.process_messages()

        assert mock_session_state.interim_summary_text == 'Test summary'

def test_process_final_summary_message(out_queue, in_queue):
    with patch('streamlit.session_state') as mock_session_state:
        mock_session_state.final_summary_text = ""
        
        processor = MessageProcessor(in_queue, out_queue)
        out_queue.put(('final_summary', 'Final test summary'))
        
        processor.process_messages()
        
        assert mock_session_state.final_summary_text == 'Final test summary'
        # Verify download_files command was queued
        assert in_queue.get() == ('download_files', None)
