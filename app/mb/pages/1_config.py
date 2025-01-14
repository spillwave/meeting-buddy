import streamlit as st
from app.mb.config import Config
import yaml
import os
from app import ROOT_PATH

st.set_page_config(page_title="Meeting Buddy - Config", page_icon="⚙️")
st.title("⚙️ Configuration")

if 'mb_config' not in st.session_state:
    st.session_state.mb_config = Config.load_config()

# Create form for configuration
with st.form("config_form"):
    st.subheader("Model Settings")
    
    local_llm_model = st.text_input(
        "Local LLM Model",
        value=st.session_state.mb_config.local_llm_model,
        help="The local LLM model to use (e.g., ollama/mistral:v0.3-32k)"
    )
    
    openai_model = st.text_input(
        "OpenAI Model",
        value=st.session_state.mb_config.openai_model,
        help="The OpenAI model to use (e.g., gpt-4)"
    )
    
    openai_api_key = st.text_input(
        "OpenAI API Key",
        value=st.session_state.mb_config.openai_api_key,
        type="password",
        help="Your OpenAI API key"
    )
    
    submitted = st.form_submit_button("Save Configuration")
    
    if submitted:
        # Update config object
        st.session_state.mb_config.local_llm_model = local_llm_model
        st.session_state.mb_config.openai_model = openai_model
        st.session_state.mb_config.openai_api_key = openai_api_key
        
        # Save to config file
        config_path = os.path.join(ROOT_PATH, 'config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(st.session_state.mb_config.__dict__, f)
        
        st.success("Configuration saved successfully!")
