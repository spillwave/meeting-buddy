import logging
import streamlit as st

logger = logging.getLogger(__name__)

class MessageProcessor:
    """Handle processing of messages between WebSocket thread and Streamlit UI."""
    
    def __init__(self, in_queue, out_queue):
        """Initialize MessageProcessor with input and output queues."""
        self.in_queue = in_queue
        self.out_queue = out_queue

    def process_messages(self):
        """Process messages from the websocket thread."""
        try:
            while not self.out_queue.empty():
                msg_type, msg_data = self.out_queue.get_nowait()

                if msg_type == "transcription":
                    st.session_state.transcription_text += msg_data + "\n"
                    st.session_state.first_transcription_received = True

                elif msg_type == "summary":
                    st.session_state.interim_summary_text = msg_data

                elif msg_type == "final_summary":
                    st.session_state.final_summary_text = msg_data
                    self.in_queue.put(("download_files", None))

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
            st.error(f"Error processing messages: {str(e)}")
