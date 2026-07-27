"""
pages/4_🤖_AI_Assistant.py

Dedicated page for the Llama-powered AI SOC Assistant.
Provides a full-screen ChatGPT-like interface.
"""

import streamlit as st

st.set_page_config(
    page_title="ISRO SOC | SOC-GPT",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ───
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif !important;
    }
    .stApp {
        background-color: #050b14 !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #050b14 0%, #08111e 100%) !important;
        border-right: 1px solid #1a2d45 !important;
    }
    
    /* Make the main area look like a chat app */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
        max-width: 900px !important;
    }
    
    /* Hide header */
    header {visibility: hidden;}
    
    .assistant-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    .assistant-header h1 {
        color: #FFFFFF;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    .assistant-header p {
        color: #A1B0C4;
        font-size: 1.1rem;
    }
    .accent {
        color: #FF9933;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="assistant-header">
        <h1><span class="accent">SOC-GPT</span></h1>
        <p>Local LLaMA 3.2 1B Instruct • Context-Aware Analytics</p>
    </div>
    """,
    unsafe_allow_html=True
)

from core.local_data_client import get_local_data_client
from core.llm_client import generate_response_stream

# Get current telemetry context
local_client = get_local_data_client()
A = local_client.get_analytics()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I'm **SOC-GPT**. I have analyzed the current telemetry on the dashboard. How can I help you hunt for threats today?"}]
    
# Render chat history
for message in st.session_state.messages:
    avatar = "🤖" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        
# Example prompts if it's a fresh chat
if len(st.session_state.messages) == 1:
    cols = st.columns(3)
    prompts = [
        "Summarize the recent critical events.",
        "What is the total anomaly count today?",
        "Are there any suspicious PowerShell activities?"
    ]
    for i, col in enumerate(cols):
        if col.button(prompts[i], use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": prompts[i]})
            st.rerun()

# Chat input at the bottom
if prompt := st.chat_input("Ask a question about the current telemetry..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
        
    with st.chat_message("assistant", avatar="🤖"):
        try:
            stream = generate_response_stream(st.session_state.messages, A)
            response = st.write_stream(stream)
        except Exception as e:
            response = f"**Error loading local LLM:** {str(e)}\n\nPlease ensure `llama-cpp-python` is installed successfully in your environment."
            st.error(response)
            
    st.session_state.messages.append({"role": "assistant", "content": response})

# ─── Sidebar Branding ───
with st.sidebar:
    st.markdown(
        """
        <div style='text-align: center; margin-bottom: 1.5rem;'>
            <h1 style='color:#FFFFFF; font-weight:800; margin:0; font-size:2rem; letter-spacing:1px;'>
                ISRO<span style='color:#FF9933;'>.</span>SOC
            </h1>
            <p style='color:#8B949E; font-size:0.75rem; margin:0; text-transform:uppercase; letter-spacing:2px; font-weight:600;'>
                SOC-GPT Engine
            </p>
        </div>
        <hr style='border-color:#1a2d45; margin:1rem 0;'>
        <p style='color:#8B949E; font-size:0.85rem; text-align:center;'>
            This assistant runs 100% locally on your hardware. No telemetry is sent outbound.
        </p>
        """,
        unsafe_allow_html=True,
    )
    
    if st.button("Clear Chat History", use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": "Hello! I'm **SOC-GPT**. I have analyzed the current telemetry on the dashboard. How can I help you hunt for threats today?"}]
        st.rerun()
