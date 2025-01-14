import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WATCH_DIRECTORY = os.path.abspath(os.path.join(ROOT_PATH, os.getenv('WATCH_DIRECTORY', './data')))
OUTPUT_DIRECTORY = os.path.abspath(os.path.join(ROOT_PATH, os.getenv('OUTPUT_DIRECTORY', './output')))
CONTEXT_DIRECTORY = os.path.abspath(os.path.join(ROOT_PATH, os.getenv('CONTEXT_DIRECTORY', './context')))

# Ensure required directories exist
for dir_path, dir_name in [
    (WATCH_DIRECTORY, 'watch'),
    (OUTPUT_DIRECTORY, 'output'),
    (CONTEXT_DIRECTORY, 'context')
]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        logger.info('Created %s directory: %s', dir_name, dir_path)


