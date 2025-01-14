import os
import pytest
import yaml
from app import ROOT_PATH
from app.mb.config import Config

os.environ.setdefault("OPENAI_API_KEY", "")
@pytest.fixture(scope="function")
def test_config():
    """Fixture to provide a custom config for testing."""
    test_config_file = os.path.join(ROOT_PATH, "app/test/test_config.yaml")

    if not os.path.exists(test_config_file):
        with open(test_config_file, 'w') as f:
            yaml.dump({}, f)

    test_config = Config.load_config(config_file_path=test_config_file)
    return test_config
