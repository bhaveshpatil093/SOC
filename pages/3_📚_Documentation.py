import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="ISRO SOC | Documentation",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS for Typography ───
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
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #050b14 0%, #08111e 100%) !important;
        border-right: 1px solid #1a2d45 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border: 1px solid #1a2d45;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0d1a2f !important;
        border-bottom: 3px solid #FF9933 !important;
        color: #FFFFFF !important;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ─── Page Header ───
st.markdown("<h1 style='color:#FFFFFF; font-weight:800; font-size:3rem; margin-bottom:0.25rem;'>Platform <span style='color:#FF9933;'>Documentation</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#A1B0C4; font-size:1.15rem; margin-bottom:2.5rem; max-width:950px; line-height:1.7;'>Comprehensive technical reference for the <b style='color:#E6EDF3;'>ISRO Security Operations Centre (SOC)</b> Analytics Engine. This manual covers the full system architecture, machine learning algorithms, deterministic threat scoring, data ingestion pipelines, ECS schema mapping, dashboard visualizations, project structure, and the complete technology stack.</p>", unsafe_allow_html=True)

# ─── Tabs ───
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "🏗️ Architecture",
    "🧠 ML Engine",
    "🎯 Threat Rules",
    "📥 Data Pipeline",
    "🗂️ ECS Schema",
    "📊 Visualizations",
    "📁 Project Structure",
    "💻 Tech Stack",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    with st.container(border=True):
        st.header("System Architecture & Design Philosophy")
        st.markdown("The ISRO SOC Analytics Platform is engineered for **absolute data sovereignty** and **high-velocity local execution**. It eschews traditional SIEM architectures (which rely on distributed databases like Elasticsearch or Splunk) in favor of an **In-Memory Vectorized Engine** that runs entirely on the operator's local machine.")
        
        st.subheader("Core Architectural Tenets")
        st.markdown("""
        * **Air-Gapped Viability:** 100% of the analytical workloads — including Machine Learning inference, feature engineering, and threat classification — execute on local hardware. No API calls or telemetry data are ever transmitted to external services.
        * **Pandas Core Vectorization:** Log data is mapped directly into RAM via the Python `pandas` library. All computations use vectorized column operations, which are orders of magnitude faster than row-by-row iteration.
        * **Singleton State Management:** The active dataset and ML models are cached in memory using Streamlit's `@st.cache_resource` decorator. This guarantees that page navigations do not re-trigger expensive model training.
        * **File-Based Cache Invalidation:** The platform monitors the data file's MD5 fingerprint. If the file changes on disk, the cache is automatically invalidated.
        """)
        
        st.divider()
        
        st.subheader("Memory Safety & Scalability")
        st.markdown("The platform dynamically adapts to the size of the ingested dataset:")
        st.markdown("""
        * **Sub-sampled ML Training:** The Isolation Forest trains on a maximum of `50,000` randomly sampled rows to prevent memory exhaustion, while still scoring *every* row in the full dataset.
        * **Schema Profiling:** Column statistics (fill rate, unique count, top-5 values) are computed on a sample of `50,000` rows to avoid OOM on wide datasets.
        * **Vectorized Flattening:** Nested ECS fields are flattened using `.apply()` instead of `iterrows()`, making the operation 50-100x faster on large datasets.
        """)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ML ENGINE
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    with st.container(border=True):
        st.header("Machine Learning Anomaly Detection Engine")
        st.markdown("The platform uses **Unsupervised Machine Learning** to detect zero-day exploits, novel lateral movement patterns, and insider threats without relying on predefined signatures. The core algorithm is the **Isolation Forest** from scikit-learn.")
        
        st.subheader("Why Isolation Forest?")
        st.markdown("""
        Traditional anomaly detection algorithms (e.g., k-NN, DBSCAN) model "normal" behavior first and then flag deviations. Isolation Forest takes the inverse approach — it explicitly isolates anomalies, making it:
        * **Computationally efficient:** Linear time complexity O(n) with low memory usage.
        * **Robust to high dimensionality:** Handles dozens of features without performance degradation.
        * **No assumption of data distribution:** Works on non-Gaussian, mixed-type security telemetry.
        """)
        
        st.subheader("Hyperparameter Configuration")
        hyper_df = pd.DataFrame([
            {"Parameter": "n_estimators", "Value": "200", "Justification": "Provides a robust ensemble. Increasing beyond 200 yields diminishing returns."},
            {"Parameter": "contamination", "Value": "0.05", "Justification": "Assumes ~5% of network telemetry is anomalous. Conservative estimate for SOCs."},
            {"Parameter": "random_state", "Value": "42", "Justification": "Fixed seed ensures reproducible results across re-runs."},
            {"Parameter": "n_jobs", "Value": "-1", "Justification": "Utilizes all available CPU cores for parallel tree construction."},
            {"Parameter": "ML_TRAIN_SAMPLE", "Value": "50,000", "Justification": "Maximum rows used for training to maintain memory safety."}
        ])
        st.table(hyper_df)
        
        st.subheader("Feature Engineering Pipeline")
        st.markdown("Raw ECS log fields are transformed into a dense numerical feature matrix before model ingestion:")
        feat_df = pd.DataFrame([
            {"Feature": "hour", "Source": "@timestamp", "Method": "Extracted hour (0-23). Captures after-hours activity."},
            {"Feature": "is_night", "Source": "Derived", "Method": "Boolean: 1 if hour < 6 or hour >= 22."},
            {"Feature": "host_enc", "Source": "host.hostname", "Method": "LabelEncoder integer. Unique numeric identity."},
            {"Feature": "host_freq", "Source": "host.hostname", "Method": "Frequency count. Rare hosts score higher."},
            {"Feature": "user_enc", "Source": "user.name", "Method": "LabelEncoder integer for user identity."},
            {"Feature": "proc_rarity", "Source": "process.name", "Method": "Inverse frequency: 1 / (count + 1). Rare processes get high values."},
            {"Feature": "cmd_len", "Source": "process.command_line", "Method": "Character length. Long commands often indicate obfuscation."},
            {"Feature": "file_size_log", "Source": "file.size", "Method": "Log-transformed file size: log(1 + size)."}
        ])
        st.table(feat_df)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — THREAT RULES
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    with st.container(border=True):
        st.header("Deterministic Threat Scoring Engine")
        st.markdown("Machine Learning identifies *structural* anomalies. The **Deterministic Rule Engine** complements this by enforcing strict, signature-based security boundaries. The final **Threat Level** is a synthesis of both outputs.")
        
        st.subheader("Detection Vectors")
        
        st.markdown("**1. LOLBin Tracking**")
        st.markdown("The engine maintains a hardcoded watchlist of high-risk binaries (Living Off The Land Binaries):")
        st.code('suspicious_procs = {"powershell.exe", "cmd.exe", "wscript.exe", "cscript.exe", "mshta.exe", "rundll32.exe", "regsvr32.exe", "certutil.exe", "bitsadmin.exe", "psexec.exe", "wmic.exe", "schtasks.exe", "net.exe", "net1.exe", "whoami.exe", "ipconfig.exe"}', language="python")
        
        st.markdown("**2. Command-Line Obfuscation**")
        st.markdown("Vectorized regex patterns scanning `process.command_line`:")
        regex_df = pd.DataFrame([
            {"Category": "Encoded Commands", "Regex": "base64 | encodedcommand | -enc | iex | invoke-expression", "MITRE": "T1059.001"},
            {"Category": "Download Cradles", "Regex": "wget | curl | downloadstring | bitstransfer", "MITRE": "T1105"},
            {"Category": "Hidden Execution", "Regex": "-w hidden | -windowstyle hidden | bypass", "MITRE": "T1564.003"}
        ])
        st.table(regex_df)
        
        st.subheader("Threat Level Synthesis Matrix")
        
        st.error("**🔴 CRITICAL THREAT**\n\n**Trigger:** Command-line matches encoded/download/hidden regex patterns OR Privileged user (SYSTEM/root) + ML anomaly flag.")
        st.warning("**🟠 HIGH THREAT**\n\n**Trigger:** Process is in the LOLBin watchlist AND the Isolation Forest flags it as anomalous (is_anomaly == True).")
        st.info("**🟣 SUSPICIOUS**\n\n**Trigger:** Process is in the LOLBin watchlist but the ML engine classifies the surrounding context as 'Normal'.")
        st.success("**🟢 NORMAL**\n\n**Trigger:** No rule triggers and ML classifies as inlier.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — DATA PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    with st.container(border=True):
        st.header("Data Pipeline & Management")
        
        st.subheader("1. Data Discovery & Auto-Detection")
        st.markdown("On startup, the system scans the `data/` directory for supported file types in priority order:")
        st.markdown("1. `.xlsx` (Excel) — read via `openpyxl`\n2. `.csv` — read via pandas\n3. `.parquet` (Columnar)")
        
        st.subheader("2. Nested Field Flattening")
        st.markdown("Raw ECS logs often contain deeply nested JSON/dict structures stored as strings. The platform identifies known dictionary columns and recursively flattens them:")
        st.code('DICT_COLS = {"agent", "process", "ecs", "data_stream", "elastic", "host", "event", "user", "file", "Effective_process"}', language="python")
        
        st.subheader("3. Dynamic Dataset Toggling")
        st.markdown("""
        Operators can upload new log files directly via the Overview Dashboard sidebar:
        * The uploaded file is persisted to `data/uploads/`
        * A radio toggle allows instant switching between datasets
        * Switching triggers a cache clear and full re-execution of the ML pipeline
        """)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — ECS SCHEMA
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    with st.container(border=True):
        st.header("Elastic Common Schema (ECS) Mapping")
        st.markdown("The platform dynamically discovers which ECS fields are present and adapts its analytics.")
        
        schema_df = pd.DataFrame([
            {"Role": "Hostname", "Candidate Fields": "host.hostname → host.name", "Usage": "KPI count, frequency encoding, host-level filtering"},
            {"Role": "Username", "Candidate Fields": "user.name", "Usage": "Identity analytics, privilege escalation detection"},
            {"Role": "Event Action", "Candidate Fields": "event.action", "Usage": "Action distribution charts, label encoding for ML"},
            {"Role": "Process Name", "Candidate Fields": "process.name", "Usage": "LOLBin matching, process tree analysis, rarity scoring"},
            {"Role": "Command Line", "Candidate Fields": "process.command_line", "Usage": "Obfuscation regex detection, command length feature"},
            {"Role": "Parent Process", "Candidate Fields": "process.parent.name", "Usage": "Parent→child process tree visualization"},
            {"Role": "Timestamp", "Candidate Fields": "@timestamp", "Usage": "Timeline visualization, temporal feature extraction"},
            {"Role": "Code Signature", "Candidate Fields": "process.code_signature.trusted", "Usage": "Code signature trust status (true/false breakdown)"},
            {"Role": "File Path", "Candidate Fields": "file.path", "Usage": "Most common file paths — detects access to sensitive directories."}
        ])
        st.table(schema_df)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — VISUALIZATIONS
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    with st.container(border=True):
        st.header("Dashboard Visualizations")
        
        st.markdown("""
        * **Overview:** Event Volume Timeline (Area chart), Threat Distribution Donut, Top Processes, Top Hosts.
        * **Threats:** Critical Events Table (Top 500 sorted by anomaly score), Threat Summary Metrics.
        * **Anomalies:** Anomaly Score Distribution (20-bin histogram), Top Anomalous Hosts, Top Anomalous Users.
        * **Patterns:** Process Tree (Parent→Child) showing attack chains, User-Process Matrix.
        * **Identity:** User Activity Distribution, User Anomaly Attribution.
        * **Code Integrity:** Code Signature Trust Breakdown, Signature Status Distribution, Hash Analysis.
        * **File Activity:** Top File Names, File Extension Breakdown.
        * **Deep Telemetry:** Full Schema Profiler showing column stats.
        * **Events:** Raw Event Browser (Filterable/Sortable DataFrame).
        """)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — PROJECT STRUCTURE
# ══════════════════════════════════════════════════════════════════════════════
with tab7:
    with st.container(border=True):
        st.header("Project Structure & File Manifest")
        
        st.code("""
SOC/
├── app.py                       # Entry point — ISRO-themed Home page
├── requirements.txt             # Python dependencies
├── .env                         # Environment config
├── config/
│   ├── __init__.py
│   └── settings.py              # Frozen dataclass — all config from .env
├── core/
│   ├── __init__.py
│   └── local_data_client.py     # Data loader, ML engine, threat scorer
├── data/
│   ├── data.xlsx                # Primary platform dataset
│   └── uploads/                 # User-uploaded datasets
├── pages/
│   ├── 1_📊_Overview.py         # Main analytics dashboard (9 tabs)
│   ├── 2_⚙️_Settings.py         # Configuration management
│   └── 3_📚_Documentation.py    # This documentation page
└── utils/                       # Shared helper utilities
        """, language="text")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — TECH STACK
# ══════════════════════════════════════════════════════════════════════════════
with tab8:
    with st.container(border=True):
        st.header("Technology Stack")
        
        tech_df = pd.DataFrame([
            {"Component": "UI Framework", "Technology": "Streamlit", "Role": "Reactive Python-to-Web frontend. State management, routing, caching."},
            {"Component": "Data Engine", "Technology": "Pandas & NumPy", "Role": "In-memory DataFrame operations. Vectorized string matching, aggregations."},
            {"Component": "Machine Learning", "Technology": "Scikit-Learn", "Role": "IsolationForest for unsupervised anomaly detection. LabelEncoder."},
            {"Component": "Visualization", "Technology": "Plotly", "Role": "Interactive, hardware-accelerated charting (Sunbursts, Treemaps)."},
            {"Component": "Excel I/O", "Technology": "openpyxl", "Role": "Backend engine for reading .xlsx files."},
            {"Component": "Runtime", "Technology": "Python 3.11+", "Role": "Leverages dataclasses, pathlib, type hints."}
        ])
        st.table(tech_df)

# ─── Sidebar ───
with st.sidebar:
    st.markdown(
        """
        <div style='text-align: center; margin-bottom: 1.5rem;'>
            <h1 style='color:#FFFFFF; font-weight:800; margin:0; font-size:2rem; letter-spacing:1px;'>
                ISRO<span style='color:#FF9933;'>.</span>SOC
            </h1>
            <p style='color:#8B949E; font-size:0.75rem; margin:0; text-transform:uppercase; letter-spacing:2px; font-weight:600;'>
                Technical Reference Manual
            </p>
        </div>
        <hr style='border-color:#1a2d45; margin:1rem 0;'>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("**DOCUMENT INDEX**")
    st.markdown(
        """
        <div style='font-size: 0.85rem; color: #A1B0C4; line-height: 2.2;'>
            <div>🏗️ System Architecture</div>
            <div>🧠 ML Anomaly Engine</div>
            <div>🎯 Deterministic Threat Rules</div>
            <div>📥 Data Pipeline & Management</div>
            <div>🗂️ ECS Schema Mapping</div>
            <div>📊 Dashboard Visualizations</div>
            <div>📁 Project Structure</div>
            <div>💻 Full Technology Stack</div>
        </div>
        <hr style='border-color:#1a2d45; margin:1rem 0;'>
        <p style='color:#8B949E; font-size:0.8rem; text-align:center;'>
            Use the tabs above to navigate between sections.
        </p>
        """,
        unsafe_allow_html=True,
    )
