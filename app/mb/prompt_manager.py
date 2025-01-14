import os
from typing import Dict
from app import logger
from app.mb.config import Config

class PromptManager:
    """Manages loading and handling of prompt files and other text content."""
    
    def __init__(self, config:Config=None):
        if not config:
            self.config = Config.load_config() # TODO: maybe we make this some singleton behavior so we aren't passing around everywhere.
        else:
            self.config = config
        self.prompts = self.load_prompts()

    def load_prompts(self) -> Dict[str, str]:
        """Load all prompt files from the prompts directory."""
        prompts_directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts')
        if not os.path.exists(prompts_directory):
            logger.error(f"Prompts directory does not exist: {prompts_directory}")
            # Create the directory if it doesn't exist
            os.makedirs(prompts_directory, exist_ok=True)
            return {}

        prompts_dict = {}
        for root, _, files in os.walk(prompts_directory):
            for file in files:
                if file.endswith(('.md', '.markdown')):
                    file_path = os.path.join(root, file)
                    base_name = os.path.splitext(file)[0]
                    with open(file_path, 'r') as f:
                        prompts_dict[base_name] = f.read()
        return prompts_dict

    def read_directory_content(self, directory_path: str) -> str:
        """Read all files in the given directory and concatenate their contents."""
        context = ""
        if os.path.exists(directory_path) and os.path.isdir(directory_path):
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                if os.path.isfile(file_path):
                    with open(file_path, 'r') as f:
                        context += f.read() + "\n"
        else:
            logger.warning(f"Directory not found: {directory_path}. Ignoring context from this directory.")
        return context

    def load_meeting_context(self) -> str:
        """Load the user-supplied meeting context note."""
        meeting_context_path = os.path.join(
            self.config.context_directory,
            self.config.user_meeting_context_file
        )
        if os.path.exists(meeting_context_path):
            with open(meeting_context_path, 'r') as f:
                return f.read()
        return ""

    def get_prompt(self, prompt_name: str) -> str:
        """Get a specific prompt by name."""
        return self.prompts.get(prompt_name, "")
