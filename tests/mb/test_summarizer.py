import os
import shutil
from app.mb.create_meeting_notes import run_summarizer
from app import OUTPUT_DIRECTORY

def test_run_summarizer_via_local(test_config):
    """Test the `run_summarizer` function."""
    # Arrange
    current_dir = os.path.dirname(os.path.abspath(__file__))

    sample_transcription = os.path.join(current_dir, '../resources/sample_transcription.txt')
    with open(sample_transcription, 'r') as f:
        transcription = f.read()

    # Put the meeting context in the expected location
    context_source = os.path.join(current_dir, '../resources/sample_meeting_context.txt')
    context_dest = os.path.join(OUTPUT_DIRECTORY, test_config.user_meeting_context_file)
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    shutil.copy2(context_source, context_dest)

    # Act
    result = run_summarizer(transcription, test_config)

    # Assert
    assert result, "The summarizer should not return an empty string."
    print(result)

def test_run_summarizer_via_openai(test_config):
    """Test the `run_summarizer` function."""
    # Arrange
    current_dir = os.path.dirname(os.path.abspath(__file__))

    if 'OPENAI_API_KEY' not in os.environ:
        assert False, "OPENAI_API_KEY environment variable is not set. CANNOT run test."

    sample_transcription = os.path.join(current_dir, '../resources/sample_transcription.txt')
    with open(sample_transcription, 'r') as f:
        transcription = f.read()

    # Put the meeting context in the expected location
    context_source = os.path.join(current_dir, '../resources/sample_meeting_context.txt')
    context_dest = os.path.join(OUTPUT_DIRECTORY, test_config.user_meeting_context_file)
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    shutil.copy2(context_source, context_dest)

    # Act
    result = run_summarizer(transcription, test_config)

    # Assert
    from pathlib import Path
    exists = Path(result).exists()

    assert exists, "The summarizer use OpenAI to create and then write a summary file and return its path."
    print(result)
