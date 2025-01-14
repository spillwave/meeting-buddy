# Standard library imports
import os
import time
import threading
import queue
import logging
import html

# Third-party imports
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Local imports
from app import ROOT_PATH
from app.mb.config import Config
from app.mb.websocket_client import websocket_client_thread

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Auto-refresh configuration
AUTO_REFRESH_INTERVAL = 1000  # Refresh every 1000 milliseconds (1 second)

st.set_page_config(
    page_title="Meeting Buddy - Home",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.title("📝 Meeting Buddy")

# Meeting Context Section
with st.expander("📝 Meeting Context", expanded=False):
    st.markdown("""
        Add any context about the meeting that should be considered when generating the summary.
        This could include:
        - Meeting agenda
        - Expected outcomes
        - Important background information
        - Key participants
        The easiest way to get this is to open the meeting invite, hit reply-all, and copy everything!
    """)

    if 'meeting_context' not in st.session_state:
        st.session_state.meeting_context = ""

    meeting_context = st.text_area(
        "Meeting Context",
        value=st.session_state.meeting_context,
        height=150,
        key="meeting_context_input"
    )

    if st.button("Save Meeting Context"):
        try:
            # Ensure watch directory exists
            os.makedirs(st.session_state.mb_config.context_directory, exist_ok=True)
            context_file_path = os.path.join(
                st.session_state.mb_config.context_directory,
                st.session_state.mb_config.user_meeting_context_file
            )
            with open(context_file_path, 'w', encoding='utf-8') as f:
                f.write(meeting_context)
            st.session_state.meeting_context = meeting_context
            st.success("Meeting context saved successfully!")
        except Exception as e:
            st.error(f"Error saving meeting context: {e}")
            logger.error(f"Error saving meeting context: {e}")

st.text_input("Meeting Title", key="meeting_title", placeholder="Enter meeting title...")

def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if 'mb_config' not in st.session_state:
        st.session_state.mb_config = Config.load_config(
            config_file_path=os.path.join(ROOT_PATH, "config.yaml")
        )
    session_vars = {
        'transcription_text': "",
        'interim_summary_text': "",
        'final_summary_text': "",
        'transcribing': False,
        'meeting_title': "Untitled Meeting",
        'last_summary_time': time.time,
        'thread_to_view_message_queue': queue.Queue,
        'view_to_thread_message_queue': queue.Queue,
        'starting': False,
        'stopping': False,
        'first_transcription_received': False,
        'download_transcription': None,
        'download_summary': None,
        'download_transcription_name': '',
        'download_summary_name': '',
        'expected_file_types': {'transcription': False, 'summary': False},
        'received_final_summary': False
    }
    for var, default in session_vars.items():
        if var not in st.session_state:
            st.session_state[var] = default() if callable(default) else default


def start_transcription():
    """Start transcription service"""
    if not st.session_state.transcribing and not st.session_state.starting:
        st.session_state.starting = True
        st.session_state.first_transcription_received = False
        try:
            # Start the websocket client in a new thread
            thread = threading.Thread(target=websocket_client_thread, args=(st.session_state.view_to_thread_message_queue,st.session_state.thread_to_view_message_queue,st.session_state.mb_config), daemon=True)
            thread.start()
            st.session_state.websocket_thread = thread
            st.session_state.transcribing = True
        except Exception as e:
            st.error(f"Error starting transcription: {e}")
            st.session_state.transcribing = False
            st.session_state.starting = False


def stop_transcription():
    """Stop transcription service"""
    if not st.session_state.transcribing or st.session_state.stopping:
        return

    st.session_state.stopping = True
    # Send stop command through queue with meeting name
    meeting_title = st.session_state.get("meeting_title", "").strip()
    if not meeting_title:
        meeting_title = "Untitled_Meeting"
    safe_meeting_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in meeting_title)
    st.session_state.view_to_thread_message_queue.put(("stop", safe_meeting_name))




def process_queue():
    """Process messages from the websocket thread"""
    if 'thread_to_view_message_queue' not in st.session_state:
        return

    try:
        while not st.session_state.thread_to_view_message_queue.empty():
            msg_type, msg_data = st.session_state.thread_to_view_message_queue.get_nowait()

            if msg_type == "transcription":
                st.session_state.transcription_text += msg_data + "\n"
                st.session_state.first_transcription_received = True

            elif msg_type == "summary":
                st.session_state.interim_summary_text = msg_data

            elif msg_type == "final_summary":
                st.session_state.final_summary_text = msg_data
                # Request file contents for download after receiving final summary
                st.session_state.view_to_thread_message_queue.put(("download_files", None))

            elif msg_type == "file_data":
                file_type = msg_data["type"]
                if file_type == "transcription":
                    st.session_state.download_transcription = msg_data["data"]
                    st.session_state.download_transcription_name = msg_data["filename"]
                elif file_type == "summary":
                    st.session_state.download_summary = msg_data["data"]
                    st.session_state.download_summary_name = msg_data["filename"]

            elif msg_type == "state_update":
                for key, value in msg_data.items():
                    if key == "transcribing":
                        st.session_state.transcribing = value
                        st.session_state.starting = False
                    else:
                        setattr(st.session_state, key, value)

            elif msg_type == "stopped":
                st.session_state.transcribing = False
                st.session_state.stopping = False

    except Exception as e:
        logger.error(f"Error processing message queue: {e}")


# Initialize session state
initialize_session_state()

# Get state variables
t = st.session_state.transcribing
starting = st.session_state.starting
stopping = st.session_state.stopping

status_message = ""
if starting:
    status_message = "Starting transcription service..."
elif stopping:
    status_message = "Stopping transcription and generating summary..."

if status_message:
    st.markdown(f"**{status_message}**")

col1, col2 = st.columns(2)
with col1:
    start_button = st.button(
        "▶️ Start",
        type='secondary',
        on_click=start_transcription,
        use_container_width=True,
        disabled=t or starting or stopping
    )

with col2:
    stop_button = st.button(
        "⏹️ Stop",
        type='primary',
        on_click=stop_transcription,
        use_container_width=True,
        disabled=not t or starting or stopping
    )

# Display transcription and summaries only when we have content
if st.session_state.first_transcription_received:
    st.markdown("""
        <style>
            .content-box {
                height: 500px;
                overflow-y: scroll;
                background-color: white;
                padding: 10px;
                border-radius: 5px;
                border: 1px solid #ddd;
            }
        </style>
    """, unsafe_allow_html=True)

    col_transcription, col_summary = st.columns(2)

    with col_transcription:
        st.subheader("Transcription")
        escaped_transcription = html.escape(st.session_state.transcription_text)
        st.markdown(f"""
            <div class="content-box">
                <pre style="white-space: pre-wrap; word-wrap: break-word;">{escaped_transcription.replace('\n', '&lt;br&gt;')}</pre>
            </div>
        """, unsafe_allow_html=True)

    with col_summary:
        st.subheader("Interim Summary")
        st.markdown(f"""
            <div class="content-box">
                {html.escape(st.session_state.interim_summary_text)}
            </div>
        """, unsafe_allow_html=True)

# Only show final summary when we have content
if st.session_state.final_summary_text:
    st.subheader("Final Summary")
    st.markdown(f"""
        <div class="content-box" style="height: 300px;">
            {html.escape(st.session_state.final_summary_text)}
        </div>
    """, unsafe_allow_html=True)

    # Display download buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.session_state.download_transcription:
            st.download_button(
                "📝 Download Transcription",
                st.session_state.download_transcription,
                file_name=st.session_state.download_transcription_name or 'transcription.txt',
                mime="application/octet-stream"
            )
    
    with col2:
        if st.session_state.download_summary:
            st.download_button(
                "📋 Download Summary",
                st.session_state.download_summary,
                file_name=st.session_state.download_summary_name or 'summary.txt',
                mime="application/octet-stream"
            )

# Process the message queue
process_queue()

# Auto-refresh the page to regularly process incoming messages
st_autorefresh(interval=AUTO_REFRESH_INTERVAL, key="auto_refresh")
