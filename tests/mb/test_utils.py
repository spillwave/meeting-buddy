import pytest
import os
from datetime import datetime
from app.mb.utils import rollover_directories, read_directory_files

def test_read_directory_files(tmp_path):
    # Create files in the temporary directory
    file1 = tmp_path / 'file1.txt'
    file2 = tmp_path / 'file2.txt'
    file1.touch()
    file2.touch()

    files = read_directory_files(str(tmp_path))
    assert len(files) == 2
    assert str(file1) in files
    assert str(file2) in files

def test_rollover_directories(tmp_path, monkeypatch):
    # Set up test directories
    watch_dir = tmp_path / 'watch'
    output_dir = tmp_path / 'output'
    context_dir = tmp_path / 'context'
    archive_dir = tmp_path / 'archive'
    
    # Create directories
    watch_dir.mkdir()
    output_dir.mkdir()
    context_dir.mkdir()
    
    # Create test files
    (watch_dir / 'test.wav').touch()
    (output_dir / 'test.txt').touch()
    (context_dir / 'context.txt').touch()
    
    # Patch directory paths
    monkeypatch.setattr('app.mb.utils.WATCH_DIRECTORY', str(watch_dir))
    monkeypatch.setattr('app.mb.utils.OUTPUT_DIRECTORY', str(output_dir))
    monkeypatch.setattr('app.mb.utils.CONTEXT_DIRECTORY', str(context_dir))
    monkeypatch.setattr('app.mb.utils.ROOT_PATH', str(tmp_path))
    
    # Test rollover with meeting name
    meeting_name = "Test Meeting"
    rollover_directories(meeting_name, include_context=True)
    
    # Verify files were moved to archive
    archive_files = list((tmp_path / 'archive').rglob('*.*'))
    assert len(archive_files) == 3  # All files should be archived
    
    # Verify original directories are empty
    assert not list(watch_dir.iterdir())
    assert not list(output_dir.iterdir())
    assert not list(context_dir.iterdir())

def test_rollover_directories_empty(tmp_path, monkeypatch):
    # Set up empty directories
    watch_dir = tmp_path / 'watch'
    output_dir = tmp_path / 'output'
    watch_dir.mkdir()
    output_dir.mkdir()
    
    monkeypatch.setattr('app.mb.utils.WATCH_DIRECTORY', str(watch_dir))
    monkeypatch.setattr('app.mb.utils.OUTPUT_DIRECTORY', str(output_dir))
    monkeypatch.setattr('app.mb.utils.ROOT_PATH', str(tmp_path))
    
    # Test rollover with empty directories
    rollover_directories("Test")
    
    # Verify no archive was created for empty directories
    assert not (tmp_path / 'archive').exists()
