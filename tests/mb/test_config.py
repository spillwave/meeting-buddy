import pytest
import os
from unittest.mock import mock_open, patch
from app.mb.config import Config

def test_load_config_from_file():
    mock_yaml_content = '''
    chunk_record_duration: 10
    audio_chunk_size: 512
    websocket_port: 8888
    '''
    with patch('builtins.open', mock_open(read_data=mock_yaml_content)):
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            config = Config.load_config('config.yaml')
            assert config.chunk_record_duration == 10
            assert config.audio_chunk_size == 512
            assert config.websocket_port == 8888

def test_load_config_defaults():
    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = False
        with patch('builtins.open', mock_open()) as mock_file:
            config = Config.load_config('config.yaml')
            assert config.chunk_record_duration == int(os.getenv('CHUNK_RECORD_DURATION', '15'))
            assert config.audio_chunk_size == int(os.getenv('AUDIO_CHUNK_SIZE', '1024'))
            assert config.websocket_port == int(os.getenv('WEBSOCKET_PORT', '9876'))
            # Verify default config was written
            mock_file().write.assert_called()

def test_config_environment_override():
    # Test that environment variables override defaults
    with patch.dict(os.environ, {
        'CHUNK_RECORD_DURATION': '20',
        'AUDIO_CHUNK_SIZE': '2048',
        'WEBSOCKET_PORT': '7777'
    }):
        config = Config()
        assert config.chunk_record_duration == 20
        assert config.audio_chunk_size == 2048
        assert config.websocket_port == 7777
