"""
core/llm_client.py

Handles downloading the local Llama model and interacting with it.
Extracts context from the dashboard's analytics to provide contextual answers.
"""

from pathlib import Path
import streamlit as st
from config import get_logger, settings

logger = get_logger(__name__)

# Constants for lightweight Llama 3.2 1B Instruct
MODEL_REPO = "bartowski/Llama-3.2-1B-Instruct-GGUF"
MODEL_FILE = "Llama-3.2-1B-Instruct-Q4_K_M.gguf"
MODEL_PATH = settings.model_save_dir / MODEL_FILE

def get_model_path() -> Path:
    """Download the model if it doesn't exist and return its path."""
    if not MODEL_PATH.exists():
        logger.info(f"Downloading model {MODEL_FILE} from huggingface_hub...")
        import huggingface_hub
        huggingface_hub.hf_hub_download(
            repo_id=MODEL_REPO,
            filename=MODEL_FILE,
            local_dir=settings.model_save_dir,
            local_dir_use_symlinks=False
        )
    return MODEL_PATH

@st.cache_resource(show_spinner="Initializing Local Llama Model (Metal/GPU Accelerated)...")
def get_llama_client():
    from llama_cpp import Llama
    path = get_model_path()
    
    # Enable metal support by setting n_gpu_layers=-1
    llm = Llama(
        model_path=str(path),
        n_ctx=4096,          # Expanded context window to hold data
        n_gpu_layers=-1,     # Offload all layers to GPU (Metal)
        verbose=False,
    )
    return llm

def generate_system_prompt(analytics: dict) -> str:
    """Injects current dashboard state into the system prompt."""
    if "error" in analytics:
        return "You are an AI SOC Assistant. There is currently an error loading data: " + analytics["error"]
        
    n_anomalies = analytics.get("n_anomalies", 0)
    threat_counts = analytics.get("threat_summary")
    
    threats_text = "No threats found."
    if threat_counts is not None and not threat_counts.empty:
        threats_text = ", ".join(f"{row['threat_level']}: {row['count']}" for _, row in threat_counts.iterrows())
        
    critical = analytics.get("critical_events")
    crit_text = "No critical events."
    if critical is not None and not critical.empty:
        # Take top 5 critical events to prevent context overflow
        top_crits = critical.head(5)
        crit_list = []
        for i, row in top_crits.iterrows():
            host = row.get("host.name", "unknown")
            user = row.get("user.name", "unknown")
            proc = row.get("process.name", "unknown")
            cmd = str(row.get("process.command_line", "none"))
            # Truncate cmd if it's too long
            if len(cmd) > 200: cmd = cmd[:200] + "..."
            crit_list.append(f"- **Host**: `{host}` | **User**: `{user}` | **Process**: `{proc}`\n  - **Cmd**: `{cmd}`")
        crit_text = "\n".join(crit_list)

    return f"""You are the ISRO Security Operations Centre (SOC) AI Assistant, an expert in cybersecurity and threat hunting.
You are running locally inside the SOC Dashboard.
You should provide precise, helpful, and professional answers based on the current telemetry data and the platform context below.

FORMAT INSTRUCTIONS: 
- ALWAYS format your response beautifully using Markdown. 
- Use bulleted lists for multiple items.
- Use `inline code` for filenames, usernames, and commands.
- Use bold text for emphasis.
- Do not dump raw unformatted text.

--- ISRO SOC PLATFORM CONTEXT ---
Architecture: You are running within an air-gapped, entirely local Python/Streamlit environment using an In-Memory Vectorized Engine (pandas) and Calamine parser. No data leaves the machine.
Machine Learning Engine: Uses Unsupervised Isolation Forest (scikit-learn) for zero-day anomaly detection. It assigns an anomaly score to every event.
Explainable AI (XAI): SHAP (SHapley Additive exPlanations) is used to calculate exactly which features contributed to an anomaly score. Higher SHAP values indicate higher threats.
Deterministic Engine: Scans command lines using regex (Base64, download cradles) and checks binaries against a LOLBin (Living Off The Land) watchlist.
Threat Synthesis: 
  - CRITICAL THREAT: Obfuscated commands or High privilege anomaly.
  - HIGH THREAT: LOLBin execution + ML Anomaly.
  - SUSPICIOUS: LOLBin execution without ML Anomaly.
  - NORMAL: No rules triggered and ML classifies as inlier.
---------------------------------

--- CURRENT SOC DASHBOARD TELEMETRY ---
Threat Summary: 
{threats_text}

Total ML Anomalies Detected: {n_anomalies}

Recent Critical Events (Top 5):
{crit_text}
---------------------------------------

When asked about the platform's capabilities, algorithms, or architecture, refer to the PLATFORM CONTEXT.
When asked about the current state, threats, or anomalies, refer ONLY to the DASHBOARD TELEMETRY data provided above.
"""

def generate_response_stream(messages: list, analytics: dict):
    """
    Generator function that yields tokens from the local LLM.
    `messages` is a list of dicts: [{"role": "user", "content": "..."}]
    """
    llm = get_llama_client()
    sys_prompt = generate_system_prompt(analytics)
    
    # Format messages for Llama 3 chat template
    prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{sys_prompt}<|eot_id|>"
    
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            prompt += f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>"
        elif role == "assistant":
            prompt += f"<|start_header_id|>assistant<|end_header_id|>\n\n{content}<|eot_id|>"
            
    prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"
    
    stream = llm(
        prompt,
        max_tokens=1024,
        stop=["<|eot_id|>", "<|end_of_text|>"],
        stream=True
    )
    
    for chunk in stream:
        delta = chunk["choices"][0].get("text", "")
        if delta:
            yield delta
