import streamlit as st
import json
import urllib3
import feedparser
import requests
import sqlite3
import time
import sys
import os
import io  # For safe in-memory file stream tracking

# Silently ignore local self-signed SSL warning flags
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Safe package router to decode binary document stream structures cleanly
try:
    import pypdf
except ImportError:
    pypdf = None

from ollama import Client
from streamlit_mic_recorder import speech_to_text

# =====================================================================
#  ☀️ INITIALIZATION & EXTRA-PREMIUM VISUAL CSS PACK (RENDER FIRST)
# =====================================================================
st.set_page_config(page_title="Agentic Workspace", page_icon="⚡", layout="wide")

# Safe Session State Keys allocation block to stop missing attribute crashes
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "active_payload" not in st.session_state:
    st.session_state.active_payload = ""
if "active_display" not in st.session_state:
    st.session_state.active_display = ""
if "speed_telemetry" not in st.session_state:
    st.session_state.speed_telemetry = "0.0 tokens/sec"

st.markdown("""
    <style>
    /* 1. RESET ALL MAIN VIEWPORT CONTAINERS TO LIGHT MODE */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    
    /* 2. OVERRIDE INPUT BOXES, DROPDOWNS, AND TEXTAREAS NATIVELY */
    div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="textarea"] {
        background-color: #f1f5f9 !important;
        border: 2px solid #cbd5e1 !important;
        border-radius: 14px !important;
    }
    
    /* Input field click focus accent ring */
    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {
        border-color: #4a90e2 !important;
        background-color: #ffffff !important;
    }
    
    /* 3. CRISP BLACK TYPOGRAPHY FORCE INJECTION */
    input, select, textarea, [data-baseweb="select"] div {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }
    
    span, p, div, label, small, h1, h2, h3, h4, h5, h6, li {
        color: #0f172a !important;
    }

    /* 4. SOLID FIX FOR DRAG-AND-DROP FILE UPLOADER BLOCKS */
    [data-testid="stFileUploader"] {
        background-color: #f8fafc !important;
        border: 2px dashed #cbd5e1 !important;
        border-radius: 14px !important;
    }
    
    [data-testid="stFileUploader"] * {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }

    /* 5. TEAM CARD CONTAINER DECORATORS (FORCE INLINE TEXT COLORS) */
    .team-box { 
        background-color: #f1f5f9 !important; 
        border: 1px solid #e2e8f0 !important; 
        padding: 14px !important; 
        border-radius: 12px !important; 
        margin-bottom: 8px !important; 
    }
    
    .team-box b, .team-box small {
        -webkit-text-fill-color: initial !important; /* Disables the global override */
    }

    /* 6. COMPONENT CARDS AND SUBMISSION BUTTONS */
    .chat-card { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; border-radius: 16px; }
    div[data-testid="stSidebar"] button, div[data-testid="stHorizontalBlock"] button {
        background-color: #f1f5f9 !important;
        border: 1px solid #e2e8f0 !important;
    }
    div[data-testid="stFormSubmitButton"] button {
        background-color: #4a90e2 !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    div[data-testid="stForm"] { border: none !important; padding: 0px !important; box-shadow: none !important; }
    
    /* 7. CUSTOM REINFORCEMENT LEARNING PILLS SCALER */
    .feedback-container { display: flex; gap: 10px; margin-top: -8px; margin-bottom: 12px; padding-left: 5px; }
    </style>
""", unsafe_allow_html=True)
chat_bubble_accent = "rgba(0,0,0,0.03)"

# =====================================================================
#  1. IDENTITY & ENVIRONMENT CONFIGURATION
# =====================================================================
LOCAL_OLLAMA_URL = "http://localhost:11434"
SQLITE_DB_FILE = "chat_history.db"

API_TOKEN = os.environ.get("API_TOKEN", "my_secret_token_731125")
NEON_DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_cOan5sF7yRTU@ep-long-lake-aolrehwr.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require")

def check_internet_connectivity():
    try:
        requests.get("https://1.1.1.1", timeout=2)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False

if "is_online" not in st.session_state:
    st.session_state.is_online = check_internet_connectivity()

# Safe client loader to prevent layout crashes if server is down
OLLAMA_HOST_ENV = os.environ.get("OLLAMA_HOST", LOCAL_OLLAMA_URL)
try:
    if st.session_state.is_online and OLLAMA_HOST_ENV != LOCAL_OLLAMA_URL:
        client = Client(host=OLLAMA_HOST_ENV, headers={"Authorization": f"Bearer {API_TOKEN}"}, verify=False)
    else:
        client = Client(host=LOCAL_OLLAMA_URL)
except Exception:
    client = None

# =====================================================================
#  🔒 LOGIN GATEWAY VALIDATION BLUEPRINT
# =====================================================================
AUTHORIZED_USERNAME = "adminmg"
AUTHORIZED_PASSWORD = "Pritam#@2006"

if "login_authenticated" not in st.session_state:
    st.session_state.login_authenticated = False

def render_login_screen():
    st.markdown("""
        <div style='text-align: center; margin-top: 50px; margin-bottom: -10px;'>
            <h1 style='font-size: 3rem; font-weight: 900; background: linear-gradient(135deg, #4a90e2, #ff7e5f); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px;'>
                ⚡ Offline Agent.Ai
            </h1>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='max-width: 450px; margin: 60px auto; padding: 36px; background-color: #ffffff; border-radius: 20px; border: 2px solid #e2e8f0; box-shadow: 0 10px 25 rgba(0, 0, 0, 0.04);'>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#0f172a; margin-top:0px; font-weight: 800; font-size: 22px;'>🔒 Security Access Control</h3>", unsafe_allow_html=True)
    st.caption("Enter credentials to unlock the Hybrid Agentic Workspace.")
    
    with st.form("security_gateway_form", clear_on_submit=False):
        input_user = st.text_input("Username Profile", placeholder="Enter username...", key="login_uid")
        input_pass = st.text_input("Password Security Key", type="password", placeholder="Enter secret password...", key="login_pwd")
        
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        submit_login = st.form_submit_button("Unlock Core Systems 🚀", use_container_width=True)
        
        if submit_login:
            if input_user == AUTHORIZED_USERNAME and input_pass == AUTHORIZED_PASSWORD:
                st.session_state.login_authenticated = True
                st.success("Access Granted! Syncing internal processing blocks...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Invalid Credentials. Network access authentication failed.")
                
    st.markdown("</div>", unsafe_allow_html=True)

if not st.session_state.login_authenticated:
    render_login_screen()
    st.stop()

# =====================================================================
#  2. HYBRID STORAGE & RL TRAINING BACKEND (UPGRADED FOR MACHINE LEARNING)
# =====================================================================
if st.session_state.is_online and NEON_DATABASE_URL and NEON_DATABASE_URL != "postgresql://neondb_owner:npg_cOan5sF7yRTU@ep-long-lake-aolrehwr.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require":
    import psycopg2
    from psycopg2.extras import DictCursor
    USING_CLOUD_DB = True
else:
    USING_CLOUD_DB = False

def get_cloud_connection():
    return psycopg2.connect(NEON_DATABASE_URL, sslmode="require")

def init_db():
    if USING_CLOUD_DB:
        try:
            conn = get_cloud_connection()
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id SERIAL PRIMARY KEY,
                    sender TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS reinforcement_feedback (
                    id SERIAL PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    reward_score INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            conn.commit()
            cursor.close()
            conn.close()
            return
        except Exception as e:
            st.warning(f"Cloud DB Initialization failed, falling back to local SQLite: {str(e)}")
            pass

    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            message_text TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reinforcement_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            reward_score INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_message(sender, text):
    if USING_CLOUD_DB:
        try:
            conn = get_cloud_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO logs (sender, message_text) VALUES (%s, %s)', (sender, text))
            conn.commit()
            cursor.close()
            conn.close()
            return
        except Exception:
            pass
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO logs (sender, message_text) VALUES (?, ?)', (sender, text))
    conn.commit()
    conn.close()

# 🧠 REINFORCEMENT LEARNING DATA LOGGER: Saves human preference parameters (+1 / -1) to log arrays
def save_rl_feedback(prompt, response, score):
    if USING_CLOUD_DB:
        try:
            conn = get_cloud_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO reinforcement_feedback (prompt, response, reward_score) VALUES (%s, %s, %s)', (prompt, response, score))
            conn.commit()
            cursor.close()
            conn.close()
            return
        except Exception:
            pass
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO reinforcement_feedback (prompt, response, reward_score) VALUES (?, ?, ?)', (prompt, response, score))
    conn.commit()
    conn.close()

def load_chat_history():
    if USING_CLOUD_DB:
        try:
            conn = get_cloud_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT sender, message_text FROM logs ORDER BY id ASC')
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return [{"role": row[0], "content": row[1]} for row in rows]
        except Exception:
            pass
    try:
        conn = sqlite3.connect(SQLITE_DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT sender, message_text FROM logs ORDER BY id ASC')
        rows = cursor.fetchall()
        conn.close()
        return [{"role": row[0], "content": row[1]} for row in rows]
    except Exception:
        return []

def get_unique_user_prompts():
    if USING_CLOUD_DB:
        try:
            conn = get_cloud_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT message_text FROM logs WHERE sender='user' ORDER BY id DESC")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return process_prompt_rows(rows)
        except Exception:
            pass
    try:
        conn = sqlite3.connect(SQLITE_DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT message_text FROM logs WHERE sender='user' ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return process_prompt_rows(rows)
    except Exception:
        return []

def process_prompt_rows(rows):
    titles = []
    seen = set()
    for row in rows:
        clean_prompt = row[0].split('\n')[0]
        if len(clean_prompt) > 30:
            clean_prompt = clean_prompt[:28] + "..."
        if clean_prompt not in seen:
            seen.add(clean_prompt)
            titles.append(clean_prompt)
    return titles[:5]

def clear_database():
    if USING_CLOUD_DB:
        try:
            conn = get_cloud_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM logs')
            conn.commit()
            cursor.close()
            conn.close()
            return
        except Exception:
            pass
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM logs')
    conn.commit()
    conn.close()

init_db()

# Lazy-load values into memory safely
if len(st.session_state.chat_history) == 0:
    st.session_state.chat_history = load_chat_history()

# --- Integrated Web Tools ---
def get_live_weather(location_query: str) -> str:
    try:
        clean_location = location_query.strip()
        if "india" not in clean_location.lower():
            clean_location += ", India"
            
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(clean_location)}&count=3&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        if not geo_res.get("results"): 
            return f"❌ Telemetry Sync Interrupted: Location mapping failed for '{location_query}'."
            
        result_node = geo_res["results"][0]
        lat, lon = result_node["latitude"], result_node["longitude"]
        resolved_name = f"{result_node.get('name')}, {result_node.get('admin1', 'India')}"
        
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,cloud_cover,surface_pressure,wind_speed_10m,wind_direction_10m&timezone=auto"
        weather_res = requests.get(weather_url, timeout=5).json()
        current = weather_res["current"]
        
        return f"""## 🌍 LIVE METEOROLOGICAL TELEMETRY: {resolved_name.upper()}
* **Core Temperature:** {current['temperature_2m']}°C
* **RealFeel (Apparent Temp):** {current['apparent_temperature']}°C
* **Relative Humidity Matrix:** {current['relative_humidity_2m']}%
* **Atmospheric Cloud Cover:** {current['cloud_cover']}%
* **Precipitation / Rain Gauge:** {current['precipitation']} mm
* **Wind Velocity Node:** {current['wind_speed_10m']} km/h (Direction: {current['wind_direction_10m']}°)
* **Surface Pressure Matrix:** {current['surface_pressure']} hPa"""
    except Exception as e:
        return f"❌ Weather Sync Failure: {str(e)}"

def get_world_news(regional_query: str) -> str:
    try:
        search_topic = regional_query.strip()
        if "india" not in search_topic.lower():
            search_topic += " India"
            
        feed_url = f"https://news.google.com/rss/search?q={requests.utils.quote(search_topic)}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(feed_url)
        
        if not feed.entries: 
            return f"⚠️ News Wire Interruption: No verified Indian press entries mapped for '{regional_query}'."
            
        article_news = f"## 📰 DISPATCH: GROUND-LEVEL LOCAL NEWS UPDATE FOR '{regional_query.upper()}'\n\n"
        for idx, entry in enumerate(feed.entries[:4]):
            clean_title = entry.title.split(" - ")[0]
            source_agency = entry.source.get('name', 'Indian Press Wire')
            article_news += f"### Segment {idx+1}: {clean_title}\n* **Press Source:** {source_agency}\n* **Published Timeline:** {entry.published}\n\n"
        return article_news
    except Exception as e:
        return f"❌ News Core Extraction Interrupted: {str(e)}"

def query_live_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        search_intent = query
        if "india" not in search_intent.lower():
            search_intent += " India"
            
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(search_intent, max_results=4)]
        if not results: 
            return "⚠️ Search Interruption: No real-time indexed information returned."
        
        compiled_matrix = f"## 🌍 REAL-TIME SEARCH ENGINE INDEX CONTEXT FOR '{query.upper()}'\n"
        for idx, item in enumerate(results):
            compiled_matrix += f"\n### Reference Source {idx+1}:\n* Title: {item.get('title')}\n* Fact Snippet: {item.get('body')}\n"
        return compiled_matrix
    except Exception as e:
        return f"❌ Search Pipeline Failure: {str(e)}"

tools_map = {"get_live_weather": get_live_weather, "get_world_news": get_world_news, "query_live_search": query_live_search}

# --- SIDEBAR CONTROL DASHBOARD ---
with st.sidebar:
    st.image("https://img.icons8.com/nolan/128/artificial-intelligence.png", width=60)
    st.title("OmniCore Systems")
    
    if st.session_state.is_online:
        st.caption("🟢 Mode: Cloud Linked (Online)")
        st.caption(f"💾 Storage: {'PostgreSQL (Neon)' if USING_CLOUD_DB else 'SQLite (Local)'}")
    else:
        st.caption("🔴 Mode: Edge Isolated (Offline)")
        st.caption("💾 Storage: SQLite (Local Fallback)")
        
    st.markdown("---")
    
    if st.button("New Chat", use_container_width=True, key="new_chat_top_btn"):
        st.session_state.active_payload = ""
        st.session_state.active_display = ""
        st.session_state.chat_history = []
        st.rerun()

    cfg_tone = st.selectbox("🎭 Persona Profile", ["Standard Agent", "Expert Professor", "Code Auditor", "Brief Summary Node"])
    
    # 📝 SUPERVISED LEARNING AGENT TRAINING INTERFACE PANEL
    st.markdown("---")
    st.subheader("🎓 Supervised Model Training")
    with st.expander("Teach & Correct Agent Response", expanded=False):
        st.caption("Create custom supervised training datasets by correcting errors:")
        with st.form("supervised_fine_tune_form", clear_on_submit=True):
            train_prompt = st.text_area("User Query Prompt", placeholder="What was your question?", height=70)
            train_target = st.text_area("Target Ground Truth Response", placeholder="Type the 100% correct answer here...", height=90)
            submit_training_node = st.form_submit_button("Log Supervised Training Entry 💾")
            
            if submit_training_node and train_prompt and train_target:
                # Save into an industry standard fine-tuning JSONL sheet architecture
                dataset_file = "supervised_fine_tuning_dataset.jsonl"
                structured_json_line = {"messages": [{"role": "system", "content": "You are Offline.Ai"}, {"role": "user", "content": train_prompt}, {"role": "assistant", "content": train_target}]}
                with open(dataset_file, "a", encoding="utf-8") as jsonl_file:
                    jsonl_file.write(json.dumps(structured_json_line) + "\n")
                st.success("✅ Logged entry to 'supervised_fine_tuning_dataset.jsonl'! Ready for model fine-tuning arrays.")

    st.markdown("---")
    st.subheader("👥 Project Team Members")
    st.markdown("""
    <div class='team-box'>
        <b style='color: #4a90e2 !important;'>Mrinal Gorain</b><br>
        <small style='color: #475569 !important;'>Lead Developer & Systems Architect</small>
    </div>
    <div class='team-box'>
        <b style='color: #2ecc71 !important;'>Prami Hazra & Sanchari Choudhury</b><br>
        <small style='color: #475569 !important;'>Documentation & Reports</small>
    </div>
    <div class='team-box'>
        <b style='color: #e67e22 !important;'>Mainak Mukherjee & Manas Banerjee</b><br>
        <small style='color: #475569 !important;'>System Evaluation Arrays</small>
    </div>
""", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("<div style='font-size: 14px; font-weight: 600; color: #4a90e2; margin-top: 15px; margin-bottom: 5px;'>Recent Chats</div>", unsafe_allow_html=True)
    recent_prompts = get_unique_user_prompts()
    
    if recent_prompts:
        for prompt_heading in recent_prompts:
            if st.button(f"💬 {prompt_heading}", key=f"hist_{prompt_heading}", use_container_width=True):
                st.session_state.active_display = prompt_heading
                st.session_state.active_payload = prompt_heading
                st.rerun()
                
    st.markdown("---")
    st.subheader("Memory Management")
    
    history_compiled_text = "\n".join([f"### {m['role'].upper()}:\n{m['content']}\n" for m in st.session_state.chat_history])
    st.download_button("Export Active Session Log (.md)", data=history_compiled_text, file_name="session_report.md", use_container_width=True)
    
    if st.button("Clear History Logs", use_container_width=True):
        clear_database()
        st.session_state.chat_history = []
        st.session_state.active_payload = ""
        st.session_state.active_display = ""
        st.rerun()
    
    st.markdown("---")
    st.subheader("🧠 Thought Stream Tracing")
    cfg_verbose = st.checkbox("Show Live Telemetry Debugner", value=True)
    st.caption(f"System RAM Footprint: {sys.getsizeof(st.session_state.chat_history)} Bytes")
    
    log_placeholder = st.empty()
    log_placeholder.info("System idle.")

    if st.button("Log Out of Session", use_container_width=True):
        st.session_state.login_authenticated = False
        st.rerun()

# =====================================================================
#  4. MAIN PANEL GRAPHICAL INTERFACE WIREFRAME
# =====================================================================
st.markdown("<h1 style='font-size: 2.5rem; font-weight: 900; background: linear-gradient(45deg, #4a90e2, #ff7e5f); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>⚡ Offline Smart Agentic Workspace</h1>", unsafe_allow_html=True)
st.caption(f"Core Computation Velocity Node: `{st.session_state.speed_telemetry}`")

# Render historical conversation streams inside isolated chat panels with custom index trackers
for current_index, message in enumerate(st.session_state.chat_history):
    with st.chat_message(message["role"]):
        st.markdown(f"<div class='chat-card'>{message['content']}</div>", unsafe_allow_html=True)
        
        # 🟢 REINFORCEMENT LEARNING INTERFACE: Appends live human preference rewards beneath Assistant responses
        if message["role"] == "assistant" and current_index > 0:
            associated_prompt = st.session_state.chat_history[current_index - 1]["content"]
            st.markdown("<div class='feedback-container'>", unsafe_allow_html=True)
            col_up, col_down, _ = st.columns([0.8, 0.9, 10.3])
            with col_up:
                if st.button("👍", key=f"up_{current_index}"):
                    save_rl_feedback(associated_prompt, message["content"], 1)
                    st.toast("Reward parameter updated: +1 (Positive Reinforcement Logged!)")
            with col_down:
                if st.button("👎", key=f"down_{current_index}"):
                    save_rl_feedback(associated_prompt, message["content"], -1)
                    st.toast("Reward parameter updated: -1 (Negative Reinforcement Logged!)")
            st.markdown("</div>", unsafe_allow_html=True)

# Quick Access Shortcut Pills
pill_cols = st.columns(3)
with pill_cols[0]:
    if st.button("🔍 Auditing Error Logs", use_container_width=True): 
        st.session_state.gemini_text_box = "Explain structural error parameters in this file context:"
        st.rerun()
with pill_cols[1]:
    if st.button("📊 Step-by-Step Math Solving", use_container_width=True): 
        st.session_state.gemini_text_box = "Solve this complex mathematical equation step-by-step:"
        st.rerun()
with pill_cols[2]:
    if st.button("📰 Daily Live News Bulletins", use_container_width=True): 
        st.session_state.gemini_text_box = "Give me real-time live weather and news updates for Nalhati, West Bengal"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# =====================================================================
#  📂 MULTIMODAL DOCUMENT & PDF DATA EXTRACTION ENGINE
# =====================================================================
file_payload_string = ""
voice_text_transcription = None

col_file, col_mic, col_spacer = st.columns([5.0, 2.5, 4.5])

with col_file:
    st.markdown("<div style='font-size: 14px; font-weight: 700; margin-bottom: 6px; color: #0f172a;'>📂 Upload Context</div>", unsafe_allow_html=True)
    uploaded_doc = st.file_uploader("Upload Context", type=["txt", "json", "c", "py", "html", "csv", "pdf"], key="gemini_file_node", label_visibility="collapsed")
    
    if uploaded_doc is not None:
        try:
            if uploaded_doc.name.lower().endswith('.pdf'):
                if pypdf is None:
                    st.error("❌ Missing Engine: 'pypdf' library is missing from the virtual environment. Run 'pip install pypdf'.")
                else:
                    pdf_byte_stream = io.BytesIO(uploaded_doc.read())
                    pdf_data_reader = pypdf.PdfReader(pdf_byte_stream)
                    extracted_pdf_text = ""
                    for operational_page_idx, individual_page in enumerate(pdf_data_reader.pages):
                        raw_page_string = individual_page.extract_text()
                        if raw_page_string:
                            extracted_pdf_text += f"\n--- Page {operational_page_idx + 1} ---\n{raw_page_string}"
                    
                    if extracted_pdf_text.strip():
                        file_payload_string = f"\n\n[SYSTEM ATTACHED FILE CONTEXT DETAILS:\nFilename: {uploaded_doc.name}\nContent:\n{extracted_pdf_text}\n]"
                    else:
                        st.warning("⚠️ Reading Warning: Uploaded PDF has no extractable text characters.")
            else:
                decoded_file_content = uploaded_doc.read().decode("utf-8", errors="ignore")
                file_payload_string = f"\n\n[SYSTEM ATTACHED FILE CONTEXT DETAILS:\nFilename: {uploaded_doc.name}\nContent:\n{decoded_file_content}\n]"
        except Exception as e:
            st.error(f"❌ Document Parsing Failed: {str(e)}")

with col_mic:
    st.markdown("<div style='font-size: 14px; font-weight: 700; margin-bottom: 6px; color: #0f172a;'>🎙️ Voice Mic</div>", unsafe_allow_html=True)
    st.markdown("<div style='background-color:#f8fafc; border:2px solid #e2e8f0; padding:9px 12px; border-radius:14px; text-align:center;'>", unsafe_allow_html=True)
    voice_text_transcription = speech_to_text(start_prompt="Record 🎙️", stop_prompt="Stop 🟥", language="en", just_once=True, key="gemini_mic_stream")
    st.markdown("</div>", unsafe_allow_html=True)
    
    if voice_text_transcription:
        st.session_state.active_display = voice_text_transcription
        st.session_state.active_payload = voice_text_transcription

# --- THE PROMPT INPUT FORM BAR ---
with st.form("multimodal_prompt_form", clear_on_submit=True):
    col_text_field, col_submit_button = st.columns([10.2, 1.8])
    
    with col_text_field:
        text_input_query = st.text_input("Prompt Box Field", placeholder="Ask Offline.Ai or utilize speech/document layers...", label_visibility="collapsed", key="gemini_text_box")
        
    with col_submit_button:
        submit_triggered = st.form_submit_button("Submit 🚀")

# 🚀 NATIVE PROCESS ROUTER: Bundles textual prompt input and context data files safely on submit action
if submit_triggered:
    cleaned_prompt_box_string = text_input_query.strip()
    if cleaned_prompt_box_string:
        if file_payload_string and uploaded_doc is not None:
            st.session_state.active_display = f"{cleaned_prompt_box_string} 📎 (Context Attached: {uploaded_doc.name})"
            st.session_state.active_payload = f"{cleaned_prompt_box_string} {file_payload_string}"
        else:
            st.session_state.active_display = cleaned_prompt_box_string
            st.session_state.active_payload = cleaned_prompt_box_string
        st.rerun()

# =====================================================================
#  5. LIVE AGENT PROCESSING LOOP
# =====================================================================
if st.session_state.active_display:
    display_user_query = st.session_state.active_display
    final_query_payload = st.session_state.active_payload
    
    st.session_state.active_display = ""
    st.session_state.active_payload = ""
    
    with st.chat_message("user"):
        st.markdown(f"<div class='chat-card'>{display_user_query}</div>", unsafe_allow_html=True)
    
    st.session_state.chat_history.append({"role": "user", "content": display_user_query})
    save_message("user", final_query_payload)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_placeholder.markdown("⏳ *Accessing intelligence matrix...*")
        
        if client is None:
            response_placeholder.error("❌ Model Integration Sync Offline: Ensure your local Ollama runtime engine is active.")
        else:
            # 🚀 SEARCH & WEATHER ROUTER INTERCEPT
            live_web_context = ""
            if st.session_state.is_online:
                user_query_lower = display_user_query.lower()
                
                # Check for weather intent
                if any(w_word in user_query_lower for w_word in ["weather", "temperature", "temp", "rain", "climate", "humidity"]):
                    if cfg_verbose:
                        log_placeholder.markdown("<div class='log-card'>Thought Trace: Intercepting regional Indian weather request...</div>", unsafe_allow_html=True)
                    extracted_loc = "Nalhati, West Bengal"
                    for word in display_user_query.split():
                        clean_w = word.strip("?,.!")
                        if clean_w.title() not in ["Live", "Weather", "Report", "Of", "In", "What", "Is", "The", "Show", "Give", "Me", "News", "And", "For"]:
                            extracted_loc = clean_w
                            break
                    live_web_context = get_live_weather(extracted_loc)
                
                # Check for news intent
                elif any(n_word in user_query_lower for n_word in ["news", "headlines", "current affairs", "bulletin"]):
                    if cfg_verbose:
                        log_placeholder.markdown("<div class='log-card'>Thought Trace: Connecting to live Indian regional news wire...</div>", unsafe_allow_html=True)
                    extracted_topic = "Nalhati West Bengal"
                    for word in display_user_query.split():
                        clean_w = word.strip("?,.!")
                        if clean_w.title() not in ["Live", "Weather", "Report", "Of", "In", "What", "Is", "The", "Show", "Give", "Me", "News", "And", "For"]:
                            extracted_topic = clean_w
                            break
                    live_web_context = get_world_news(extracted_topic)
                
                # Standard Search Intent Fallback
                else:
                    if cfg_verbose:
                        log_placeholder.markdown("<div class='log-card'>Thought Trace: Deploying DuckDuckGo target indices...</div>", unsafe_allow_html=True)
                    live_web_context = query_live_search(display_user_query)

            system_rules = f"""
You are a premium hybrid AI agent operating smoothly in both online and offline network frames.
Your name is 'Offline.Ai', developed by Mrinal Gorain, a student of Nalhati Government Polytechnic, Branch of CST.

PROJECT DOCUMENTATION CREDIT DIRECTIVE:
- The project documentation and report creation were entirely designed and created by Prami Hazra and Sanchari Choudhury.

REQUIRED REINFORCED PERSONA STYLE TONE MATRIX:
- Current active persona setting to maintain: {cfg_tone}

CRITICAL TRUTH & RECONCILIATION DIRECTIVE:
- You must prioritize factual truth using the provided real-time context data blocks.
- Since you are updating weather and news parameters across India down to local states, cities, and villages, output data exactly as formatted by your tools. Do not modify numbers, dates, or temperatures.
- If the tool explicitly returns structured reference segments, summarize them clearly and provide true information without adding outside assumptions.

CRITICAL MATHEMATICAL LATEX GUARDRAILS:
- You can solve any complex engineering mathematics step-by-step.
- Use $inline$ markers for equations within running text sentences.
- Use $$display$$ markers for major standalone equations or derivations.

CRITICAL MULTILINGUAL LANGUAGE MATRIX DIRECTIVE:
- You understand English, Hindi, Bengali, Hinglish, and Benglish.
  1. If the user asks a question in Bengali OR romanized Benglish text, translate and reply 100% inside pure BENGALI SCRIPT (বাংলা হরফ) only.
  2. If the user asks a question in Hindi OR romanized Hinglish text, translate and reply 100% inside pure HINDI SCRIPT (देवनागरी) only.
  3. If the user asks in standard English, reply in standard English.

CURRENT REAL-TIME DATA MATRIX:
{live_web_context if live_web_context else 'System running on local base knowledge weights.'}
"""

            agent_context = [{"role": "system", "content": system_rules}]
            for past_msg in st.session_state.chat_history[-4:]:
                agent_context.append({"role": past_msg["role"], "content": past_msg["content"]})
                
            agent_context.append({"role": "user", "content": final_query_payload})

            try:
                start_time = time.time()
                stats_tracker = [0]
                
                def text_stream_generator():
                    stream_res = client.chat(
                        model="llama3", 
                        messages=agent_context, 
                        stream=True,
                        options={"temperature": 0.1, "num_thread": 4}
                    )
                    yield "<div class='chat-card'>"
                    for chunk in stream_res:
                        stats_tracker[0] += 1
                        yield chunk['message']['content']
                    yield "</div>"

                full_response = response_placeholder.write_stream(text_stream_generator())
                elapsed_time = time.time() - start_time
                if elapsed_time > 0:
                    st.session_state.speed_telemetry = f"{round(stats_tracker[0] / elapsed_time, 1)} tokens/sec"
                    
                st.session_state.chat_history.append({"role": "assistant", "content": full_response})
                save_message("assistant", full_response)
            except Exception as conn_err:
                response_placeholder.error(f"⚠️ Runtime Token Decoder Exception: {str(conn_err)}")

        st.components.v1.html("""
            <script>
                var chatWindow = window.parent.document.querySelector('.main');
                if (chatWindow) { chatWindow.scrollTo({ top: chatWindow.scrollHeight, behavior: 'smooth' }); }
            </script>
        """, height=0)
        st.rerun()