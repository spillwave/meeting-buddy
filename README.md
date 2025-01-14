TODO:
DONE - * Fix integration w/threads (Chris)
DONE - * Make streamlit start/stop to run record/transcribe from UI (Chris)
DONE - * Summarize minute chunks with local llm (Chris)
DONE - * Show minute-summaries rolling (Chris)
DONE - * Only do big LLM summary at the end (Chris)
DONE - * Spinners and lock for clearer "processing" signaling 
DONE - * Download buttons for summary/transcript working
DONE - * Upload button/storage for meeting notes path/files

Left Off
* Bug- debug the summarizer to ensure prompt selection by timeframe is working
* Bug- final summarization not working
* 

* Upload button/storage for meeting context path/files
* Clean up file-system/archiving and make a nice listing on a second tab to view prior meetings
* Summary extracted to json used for the render & possibly graph storage (Rick) 
* Graph integration of meetings (Rick)
* Graph integration of documentation


# Meeting Buddy

Meeting Buddy is an automated system for recording, transcribing, and generating meeting notes in real-time. It captures audio in 15-second intervals, transcribes the audio using Whisper, and generates comprehensive meeting notes using OpenAI's GPT models.

## Features

- Real-time audio recording and transcription
- Automatic meeting notes generation
- Live transcript and meeting notes viewing
- Question detection for interviews
- Support for behavioral, programming, and system design questions

## Prerequisites

- Python 3.12.7
- Conda package manager
- OpenAI API key
- FFmpeg (for Whisper transcription)

## Installation

export PATH="$(brew --prefix)/opt/python@3.12/libexec/bin:$PATH"

1. Create a new conda environment:
```bash
python -m venv venv
source venv/bin/activate
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

3. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key-here'
```

## Core Components

| Program | Description | How to Run |
|---------|-------------|------------|
| record.py | Records audio in 15-second intervals | `python record.py` |
| transcribe.py | Transcribes audio files using Whisper | `python transcribe.py` |
| combine_all.py | Combines transcription files | `python combine_all.py` |
| create_meeting_notes.py | Generates meeting notes using GPT | `python create_meeting_notes.py` |
| view.py | Web interface for viewing meeting notes | `streamlit run view.py` |
| transcripts_viewer.py | Web interface for viewing transcripts | `streamlit run transcripts_viewer.py` |
| question_detector.py | Detects interview questions | `python question_detector.py` |
| answer_creator.py | Generates answers for detected questions | `python answer_creator.py` |
| answer_viewer.py | Web interface for viewing answers | `streamlit run answer_viewer.py` |

## Getting Started

1. Set up a .env file in the project root:
```properties
CHUNK_RECORD_DURATION=2
WATCH_DIRECTORY=../../data
OUTPUT_DIRECTORY=../../output
```

2. Set up your environment:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
source env.sh
```

### Running the Application

There are two ways to start the application:

1. Using the shell script (recommended):
```bash
./run_app.sh
```

2. Using Python directly:
```bash
python app/mb/run_app.py
```

Both methods will start both the WebSocket service and the Streamlit interface. The application will be available at http://localhost:8501

### Development Setup

For development, you might want to run the service and UI separately:

1. Start the WebSocket service:
```bash
python app/mb/service.py
```

2. In a separate terminal, start the Streamlit interface:
```bash
streamlit run app/pages/home.py
```

This setup allows you to modify and restart either component independently during development.

## WebSocket Test Client

For testing and debugging the WebSocket service, you can use the included test client. The client allows you to manually interact with a running service instance.

### Usage

Make sure the service is running first (`python -m app/mb/service.py`), then start the test client:

```bash
python -m app.mb.socket_test
```

Available commands in interactive mode:

- `start` - Start recording
- `stop [meeting_name]` - Stop recording (meeting name optional)
- `summarize <text>` - Request summary of provided text
- `listen` - Start listening for messages in background
- `stoplisten` - Stop listening for messages
- `quit` - Exit the program

Example usage:
```bash
Enter command> start
Enter command> listen
Received: {"type": "transcription", "text": "..."}
Enter command> stoplisten
Enter command> stop my_meeting
Enter command> quit
```

By default, the client connects to `ws://localhost:8765`. You can specify a different URI using the `--uri` argument:
```bash
python -m app.mb.socket_test --uri ws://localhost:9000
