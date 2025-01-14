# Meeting Buddy

Meeting Buddy is an automated system for recording, transcribing, and generating meeting notes in real-time. It captures audio in 15-second intervals, transcribes the audio using Whisper, and generates comprehensive meeting notes using OpenAI's GPT models.

## Features

- Real-time audio recording and transcription
- Automatic meeting notes generation
- Live transcript and meeting notes viewing
- Question detection for interviews
- Support for behavioral, programming, and system design questions

## Prerequisites

- Python 3.12
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

## Getting Started

After you first run the program, you will have a config.yaml file in your program folder.
You may check this to see any options you want to update.

### Sample Config.yaml
If you want to get started with a valid file rather than waiting for the generated 
defaults, here's the current blueprint. Note this may change across releases.

You'll want to make sure you set valid values for your own accounts for things like:

openai_api_key
openai_model

Or use the app config panel to do so.

```yaml
audio_channels: 1
audio_chunk_size: 1024
audio_rate: 44100
check_interval: 120
chunk_record_duration: 15
combine_interval: 5
context_directory: /Users/[your user]/chris/ai-dev/meeting_buddy/context
local_llm_model: ollama/mistral:v0.3-32k
log_level: INFO
meeting_notes_file: meeting_notes_summary.md
meeting_prompt_file: app/prompts/meeting_prompt.md
monitor_interval: 1
openai_api_key: ...
openai_model: gpt-4o-2024-11-20
output_directory: /Users/cmathias/chris/ai-dev/meeting_buddy/output
prompts_directory: /Users/cmathias/chris/ai-dev/meeting_buddy/app/prompts
summary_interval: 5
transcribe_interval: 1
user_meeting_context_file: meeting_context_note.txt
watch_directory: /Users/cmathias/chris/ai-dev/meeting_buddy/data
websocket_port: 9876
whisper_model: base

```
### Running the Application

There are three ways to start the application

All methods will start both the WebSocket service and the Streamlit interface. 
The application will be available at http://localhost:8501:

1. Use Docker
```shell
TODO
```

2. Using the shell script (recommended):
```bash
./run_app.sh
```

3. Using Python directly:
```bash
python app/mb/run_app.py
```

## Developing

1. Set up your environment:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Optional Env
You can create an env.sh that has config values you don't want exposed, e.g.
```env.sh
export OPENAI_API_KEY=[your key]
```

and then
```shell
source env.sh
```


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

By default, the client connects to `ws://localhost:{config.websocket_port}`. You can specify a different URI using the `--uri` argument:
```bash
python -m app.mb.socket_test --uri ws://localhost:9000
```