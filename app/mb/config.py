import os
from dataclasses import dataclass
import yaml
from app import ROOT_PATH, WATCH_DIRECTORY, OUTPUT_DIRECTORY, CONTEXT_DIRECTORY

@dataclass
class Config:
    """Configuration settings for the meeting bot services."""
    # Recording settings
    chunk_record_duration: int = int(os.getenv('CHUNK_RECORD_DURATION', '15'))
    audio_chunk_size: int = int(os.getenv('AUDIO_CHUNK_SIZE', '1024'))
    audio_channels: int = int(os.getenv('AUDIO_CHANNELS', '1'))
    audio_rate: int = int(os.getenv('AUDIO_RATE', '44100'))

    # Transcription settings
    whisper_model: str = os.getenv('WHISPER_MODEL', 'base')
    transcribe_interval: int = int(os.getenv('TRANSCRIBE_INTERVAL', '1'))

    # Combiner settings
    combine_interval: int = int(os.getenv('COMBINE_INTERVAL', '5'))

    # Monitor settings
    monitor_interval: int = int(os.getenv('MONITOR_INTERVAL', '1'))

    # Websocket settings
    websocket_port: int = int(os.getenv('WEBSOCKET_PORT', '9876'))

    # File paths from app.__init__
    watch_directory: str = WATCH_DIRECTORY
    output_directory: str = OUTPUT_DIRECTORY
    context_directory: str = CONTEXT_DIRECTORY
    prompts_directory: str = os.path.abspath(os.path.join(ROOT_PATH, 'app/prompts'))

    # Meeting notes settings
    meeting_prompt_file: str = os.getenv('MEETING_PROMPT_FILE', 'app/prompts/meeting_prompt.md')
    meeting_notes_file: str = os.getenv('MEETING_NOTES_FILE', 'meeting_notes_summary.md')
    user_meeting_context_file: str = "meeting_context_note.txt"
    openai_model: str = os.getenv('OPENAI_MODEL', 'gpt-4o')
    check_interval: int = int(os.getenv('CHECK_INTERVAL', '120'))
    summary_interval: int = int(os.getenv('SUMMARY_INTERVAL', '5'))
    log_level: int = os.getenv('log_level', 'INFO')
    local_llm_model: str = os.getenv('LLM_MODEL', 'ollama/mistral:v0.3-32k')
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')

    @classmethod
    def load_config(cls, config_file_path=None):
        """Load configuration from config.yaml or create default."""
        if not config_file_path:
            config_file_path = os.path.join(ROOT_PATH, 'config.yaml')

        if config_file_path and os.path.exists(config_file_path):
            config_data = yaml.safe_load(open(config_file_path))
            return cls(**config_data)
        else:
            # Create default config
            # TODO: this should probably defer to env versions even when file already exists...?
            config = cls()
            with open(os.path.join(ROOT_PATH, 'config.yaml'), 'w') as f:
                yaml.dump(config.__dict__, f)
            return config
