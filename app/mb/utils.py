import os
import shutil
from datetime import datetime
from app import logger, WATCH_DIRECTORY, OUTPUT_DIRECTORY, CONTEXT_DIRECTORY, ROOT_PATH


def rollover_directories(meeting_name: str = "", include_context: bool = False):
    """Archive existing directory contents with timestamp and meeting name.
    
    Args:
        meeting_name: Name of the meeting for archival
        include_context: Whether to include CONTEXT_DIRECTORY in rollover (typically True only on stop)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # Sanitize meeting name for file system
    safe_meeting_name = meeting_name.strip().replace(' ', '_')
    safe_meeting_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in safe_meeting_name)
    prefix = f"{safe_meeting_name}_" if safe_meeting_name else ""

    directories = [WATCH_DIRECTORY, OUTPUT_DIRECTORY]
    if include_context:
        directories.append(CONTEXT_DIRECTORY)

    for directory in directories:
        if os.path.exists(directory) and os.listdir(directory):
            # Create archive directory if it doesn't exist
            archive_dir = os.path.join(ROOT_PATH, 'archive')
            os.makedirs(archive_dir, exist_ok=True)

            # Create timestamped directory
            timestamped_dir = os.path.join(archive_dir, f'{os.path.basename(directory)}_{prefix}{timestamp}')
            os.makedirs(timestamped_dir)

            # Move all files to archived directory
            for item in os.listdir(directory):
                src = os.path.join(directory, item)
                dst = os.path.join(timestamped_dir, item)
                shutil.move(src, dst)

            logger.info(f"Archived contents of {directory} to {timestamped_dir}")

def read_directory_files(directory: str):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_list.append(os.path.join(root, file))
    return file_list
