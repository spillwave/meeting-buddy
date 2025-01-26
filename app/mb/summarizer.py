import asyncio
import os
import time
from openai import OpenAI
import logging
from mb.config import Config
from app import CONTEXT_DIRECTORY
from mb.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class MeetingNotesGenerator:
    """Handles the generation of meeting notes from transcriptions using OpenAI."""

    def __init__(self, config, service=None, prompt_manager=None):
        """Initialize the MeetingNotesGenerator with configuration.
        
        Args:
            config: Configuration instance
            service: Optional Service instance
            prompt_manager: Optional PromptManager instance
        """
        self.config = config or Config.load_config()
        self.service = service
        self.prompt_manager = prompt_manager or PromptManager(self.config)
        self.client = None
        if config.openai_api_key or os.getenv('OPENAI_API_KEY'):
            self.client = OpenAI(
                api_key=config.openai_api_key or os.getenv('OPENAI_API_KEY'),
                timeout=60.0
            )
        else:
            logging.warning(f'OPENAI_API_KEY environment variable is not set. Final summary will be created using {self.config.local_llm_model}.')

        self.prompt_manager = PromptManager()
        self.meeting_notes_path = os.path.join(CONTEXT_DIRECTORY, self.config.meeting_notes_file)

    def send_to_openai(self, prompt: str, content: str) -> str:
        """Send the content to OpenAI API and return the response."""
        if not self.client:
            logging.error("OpenAI client not initialized")
            return ""

        try:
            response = self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"Error when calling OpenAI API: {e}")
            return ""

    def backup_meeting_notes(self):
        """Back up the existing meeting notes file before overwriting."""
        if os.path.exists(self.meeting_notes_path):
            base_dir = os.path.dirname(self.meeting_notes_path)
            base_name = os.path.splitext(os.path.basename(self.meeting_notes_path))[0]
            ext = os.path.splitext(self.meeting_notes_path)[1]
            N = 1
            while True:
                backup_filename = os.path.join(base_dir, f"{base_name}{N}{ext}")
                if not os.path.exists(backup_filename):
                    os.rename(self.meeting_notes_path, backup_filename)
                    logging.info(f"Backed up {self.meeting_notes_path} to {backup_filename}")
                    break
                else:
                    N += 1
        else:
            logging.debug("No existing meeting notes to back up.")

    async def generate_notes(self, transcription: str) -> str:
        big_model_available = True
        """Generate meeting notes from the transcription."""
        if not self.client:
            logging.warning(f"OPENAI_API_KEY environment variable not set. Using local model {self.config.local_llm_model} instead for final summarization.")
            big_model_available = False

        try:
            # Load the prompt and meeting context
            prompt = self.prompt_manager.get_prompt("meeting_prompt")
            meeting_context = self.prompt_manager.load_meeting_context()

            # Read additional context from directories
            additional_context_content = ""

            # Combine content and context
            full_content = f"{additional_context_content}\n{meeting_context}\n{transcription}"

            if not transcription.strip():
                logging.warn("Error in meeting notes generator: No content found in transcription.")
                return "Error in meeting notes generator: No content found in transcription."

            if big_model_available:
                logging.info("Sending content to OpenAI API.")
                try:
                    response = self.send_to_openai(prompt, full_content)
                except Exception as e:
                    logging.error(f"Error when calling OpenAI API: {e} - switching to local")
                    response = await self.service.summarize_text(full_content, prompt)
            else:
                response = await self.service.summarize_text(full_content, prompt)

            if response:
                self.backup_meeting_notes()
                response_adjusted_markdown = response.replace('•', '*')
                with open(self.meeting_notes_path, 'w') as f:
                    f.write(response_adjusted_markdown)
                logging.info(f"Meeting notes saved to {self.meeting_notes_path}")
                return response_adjusted_markdown
            else:
                logging.error("No response received from final-summarization model api.")
                raise Exception(f"No response received from model api.")

        except Exception as e:
            logging.error(f"Error in meeting notes generator: {e}")
            raise Exception(f"Error in meeting notes generator: {e}")

def run_summarizer(transcription: str, config, service=None, prompt_manager=None) -> str:
    """Main summarization function designed to run in a thread."""
    try:
        generator = MeetingNotesGenerator(config, service, prompt_manager)
        # Don't create a new event loop if we're already in one
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(generator.generate_notes(transcription))
        except RuntimeError:
            # No event loop exists, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(generator.generate_notes(transcription))
            finally:
                loop.close()
    except Exception as e:
        logging.error(f"Error in run_summarizer: {str(e)}", exc_info=True)
        return f"Error generating final summary: {str(e)}"
