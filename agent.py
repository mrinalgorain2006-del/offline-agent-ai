import streamlit as st
import json
import urllib3
import feedparser
import requests
import sqlite3
import time
import sys
import os
from ollama import Client
from streamlit_mic_recorder import speech_to_text

# Silently ignore local self-signed SSL warning flags
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
#  1. IDENTITY & ENVIRONMENT FALLBACK CONFIGURATION
# =====================================================================
CADDY_URL = "https://127.0.0.1:8080"
LOCAL_OLLAMA_URL = "http://localhost:11434"
SQLITE_DB_FILE = "chat_history.db"

API_TOKEN = os.environ.get("API_TOKEN", "my_secret_token_731125")
NEON_DATABASE_URL = os.environ.get("DATABASE_URL", "YOUR_NEON_CONNECTION_STRING_HERE")

# =====================================================================
#  🌐 REAL-TIME LIVE INTERNET CONNECTIVITY CHECKER NODE
# =====================================================================
def check_internet_connectivity():
    try:
        # Pinging a highly stable public DNS server with a strict 2-second latency timeout
        requests.get("https://1.1.1.1", timeout=2)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False

if "is_online" not in st.session_state:
    st.session_state.is_online = check_internet_connectivity()

# Instantiating the correct Ollama compilation target based on network availability
if st.session_state.is_online:
    client = Client(host=CADDY_URL, headers={"Authorization": f"Bearer {API_TOKEN}"}, verify=False)
else:
    client = Client(host=LOCAL_OLLAMA_URL)

# =====================================================================
#  🔒 LOGIN GATEWAY VALIDATION BLUEPRINT (FIXED FOR TITLE & ENTER KEY)
# =====================================================================
AUTHORIZED_USERNAME = "adminmg"
AUTHORIZED_PASSWORD = "Pritam#@2006"

if "login_authenticated" not in st.session_state:
    st.session_state.login_authenticated = False

def render_login_screen():
    # Renders the premium title header first so it is visible in the top box area
    st.markdown("""
        <div style='text-align: center; margin-top: 40px; margin-bottom: -20px;'>
            <h1 style='font-size: 2.8rem; font-weight: 800; background: linear-gradient(45deg, #4a90e2, #ff7e5f); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px;'>
                ⚡ Offline Agent.Ai
            </h1>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='max-width: 450px; margin: 80px auto; padding: 30px; background-color: var(--secondary-background-color); border-radius: 15px; border: 1px solid rgba(128, 128, 128, 0.2); box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.05);'>", unsafe_allow_html=True)
    st.title("🔒 Security Access Control")
    st.caption("Enter credentials to unlock the Hybrid Agentic Workspace.")
    
    # Wrapped inputs inside a Streamlit form to allow instant "Enter" key submission from keyboard
    with st.form("security_gateway_form", clear_on_submit=False):
        input_user = st.text_input("Username Profile", placeholder="Enter username...", label_visibility="visible")
        input_pass = st.text_input("Password Security Key", type="password", placeholder="Enter secret password...", label_visibility="visible")
        
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
    st.set_page_config(page_title="Security Gateway", page_icon="🔒", layout="wide")
    render_login_screen()
    st.stop()

# Set main page config to wide mode to guarantee full-screen layout usage
st.set_page_config(page_title="Agentic Workspace", page_icon="⚡", layout="wide")

# =====================================================================
#  2. HYBRID STORAGE BACKEND (POSTGRESQL OR SQLITE ROUTER)
# =====================================================================
if st.session_state.is_online and NEON_DATABASE_URL and NEON_DATABASE_URL != "YOUR_NEON_CONNECTION_STRING_HERE":
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
                )
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

# --- Integrated Web Tools ---
def get_live_weather(city: str) -> str:
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city.strip()}&count=1&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=5).json()
        if not geo_res.get("results"): return f"❌ Meteorological Error: Location tracking failed for '{city}'."
        lat, lon = geo_res["results"][0]["latitude"], geo_res["results"][0]["longitude"]
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,cloud_cover,surface_pressure,wind_speed_10m"
        weather_res = requests.get(weather_url, timeout=5).json()
        current = weather_res["current"]
        return f"""## 🌍 WEATHER Telemetry FOR {city.upper()}\n* Core Temp: {current['temperature_2m']}°C\n* Apparent Temp: {current['apparent_temperature']}°C\n* Humidity: {current['relative_humidity_2m']}%"""
    except Exception as e:
        return f"❌ Weather Sync Interrupted: {str(e)}"

def get_world_news(topic: str) -> str:
    try:
        feed_url = f"https://news.google.com/rss/search?q={requests.utils.quote(topic.strip())}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(feed_url)
        if not feed.entries: return f"⚠️ News Wire Interruption: No live bulletins currently indexed for '{topic}'."
        article_news = f"## 📰 DISPATCH: EDITORIAL LIVE NEWS ANALYSIS FOR '{topic.upper()}'\n\n"
        for i, entry in enumerate(feed.entries[:3]):
            article_news += f"### Segment {i+1}: {entry.title}\n* Press Source: **{entry.source.get('name')}**\n\n"
        return article_news
    except Exception as e:
        return f"❌ News Error: {str(e)}"

def query_live_search(query: str) -> str:
    try:
        search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(search_url, headers=headers, timeout=6)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        results = soup.find_all("a", class_="result__snippet")
        if not results: return get_world_news(query)
        article_search = f"## 📰 DISPATCH: REAL-TIME SEARCH INDEX MATRIX FOR '{query.upper()}'\n\n"
        for i, res in enumerate(results[:3]):
            article_search += f"### Segment {i+1}:\n{res.get_text().strip()}\n\n"
        return article_search
    except Exception as e:
        return f"❌ Search Pipeline Failure: {str(e)}"

tools_map = {"get_live_weather": get_live_weather, "get_world_news": get_world_news, "query_live_search": query_live_search}

# =====================================================================
#  3. VISUAL PREMIUM STYLING & IMMERSIVE PAGE LAYOUT (ADAPTIVE THEMES)
# =====================================================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = load_chat_history()
if "active_payload" not in st.session_state:
    st.session_state.active_payload = ""
if "active_display" not in st.session_state:
    st.session_state.active_display = ""
if "speed_telemetry" not in st.session_state:
    st.session_state.speed_telemetry = "0.0 tokens/sec"

st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        user-select: text !important; -webkit-user-select: text !important; -moz-user-select: text !important; -ms-user-select: text !important;
    }
    html { scroll-behavior: smooth; }
    
    /* Variable design layout system cards */
    .log-card { 
        background-color: var(--secondary-background-color); 
        color: var(--text-color); 
        padding: 15px; 
        border-radius: 10px; 
        margin-bottom: 10px; 
        border-left: 5px solid #4a90e2; 
        border: 1px solid rgba(128, 128, 128, 0.15);
    }
    .team-card { 
        background-color: rgba(128, 128, 128, 0.06); 
        color: var(--text-color); 
        padding: 12px; 
        border-radius: 8px; 
        border: 1px solid rgba(128, 128, 128, 0.15); 
        margin-top: 5px; 
        margin-bottom: 8px; 
    }
    
    /* Widescreen Action Block alignments matching reference look */
    .action-panel-container {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 15px !important;
        margin-top: 15px;
        margin-bottom: 15px;
    }
    .custom-upload-box {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        color: var(--text-color) !important;
        border-radius: 10px;
        padding: 12px 18px;
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
    }
    .custom-mic-box {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 46px !important;
        width: 48px !important;
    }
    .custom-mic-box div, .custom-mic-box button {
        background-color: var(--secondary-background-color) !important;
        color: var(--text-color) !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        border-radius: 10px !important;
        height: 46px !important;
        width: 48px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: none !important;
    }
    
    /* Floating action entry prompt bar */
    .premium-prompt-bar {
        background-color: var(--secondary-background-color); 
        border: 1px solid rgba(128, 128, 128, 0.25); 
        padding: 6px 14px; 
        border-radius: 24px; 
        display: flex !important; 
        flex-direction: row !important; 
        align-items: center !important; 
        justify-content: space-between !important; 
        width: 100% !important;
        margin-top: 5px;
    }
    
    /* Clean overrides for base input containers */
    .stTextInput>div>div>input { 
        background-color: transparent !important; 
        color: var(--text-color) !important; 
        border: none !important; 
        box-shadow: none !important; 
        font-size: 15px !important; 
        padding: 4px 8px !important; 
        height: 38px !important; 
    }
    .stButton>button { 
        height: 38px !important; 
        border-radius: 18px !important; 
        padding: 0px 14px !important; 
        background-color: rgba(128, 128, 128, 0.08) !important; 
        border: 1px solid rgba(128, 128, 128, 0.15) !important; 
        color: var(--text-color) !important; 
    }
    .history-title { font-size: 14px; font-weight: 600; color: #4a90e2; margin-top: 15px; margin-bottom: 5px; }
    
    /* Clean alignment structure for standard file uploader button widgets */
    .stFileUploader section[data-testid="stFileUploadDropzone"] { border: none !important; padding: 0px !important; background: transparent !important; display: flex !important; align-items: center !important; }
    .stFileUploader section[data-testid="stFileUploadDropzone"] div { display: none !important; }
    .stFileUploader section[data-testid="stFileUploadDropzone"] button { display: block !important; padding: 2px 14px !important; background-color: rgba(128, 128, 128, 0.12) !important; color: var(--text-color) !important; border-radius: 6px !important; font-size: 13px !important; height: 30px !important; border: 1px solid rgba(128, 128, 128, 0.15) !important; }
    .stFileUploader label { display: none !important; }
    .stFileUploader div[data-testid="stFileUploaderFileName"] { color: var(--text-color) !important; font-size: 12px; margin-left: 10px !important; margin-top: 0px !important; }
    
    div[data-testid="stForm"], div[data-testid="stForm"]>div, fieldset { border: none !important; padding: 0px !important; box-shadow: none !important; margin: 0px !important; }
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR CONTROL DASHBOARD ---
with st.sidebar:
    st.image("https://img.icons8.com/nolan/128/artificial-intelligence.png", width=80)
    st.title("OmniCore Systems")
    
    if st.session_state.is_online:
        st.caption("🟢 Mode: Cloud Linked (Online)")
        st.caption(f"💾 Storage: {'PostgreSQL (Neon)' if USING_CLOUD_DB else 'SQLite (Local)'}")
    else:
        st.caption("🔴 Mode: Edge Isolated (Offline)")
        st.caption("💾 Storage: SQLite (Local Fallback)")
        
    st.markdown("---")
    
    # 🌓 UI Workspace Theme Controller
    st.subheader("🌓 UI Workspace Theme")
    theme_selection = st.radio(
        "Toggle Layout View",
        ["☀️ Light Mode Default", "🌙 Dark Mode Premium"],
        index=0,  # Enforces Light Mode as primary out-of-the-box system default
        label_visibility="collapsed"
    )
    
    # Dynamic CSS Variables inheritance pipeline that changes based on theme choice
    if theme_selection == "☀️ Light Mode Default":
        st.markdown("""
            <style>
            .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] { background-color: #ffffff !important; color: #31333f !important; }
            :root { --text-color: #31333f !important; --secondary-background-color: #f0f2f6 !important; }
            </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
            .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] { background-color: #0e1117 !important; color: #fafafa !important; }
            :root { --text-color: #fafafa !important; --secondary-background-color: #1d2430 !important; }
            </style>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    if st.button("➕ New Chat", use_container_width=True, key="new_chat_top_btn"):
        st.session_state.active_payload = ""
        st.session_state.active_display = ""
        st.session_state.chat_history = []
        st.rerun()

    cfg_tone = st.selectbox("🎭 Persona Profile", ["Standard Agent", "Expert Professor", "Code Auditor", "Brief Summary Node"])
    
    st.markdown("---")
    st.subheader("👥 Project Team Members")
    st.markdown("<div class='team-card'><b style='color:#4a90e2;'>Mrinal Gorain</b><br><small>💡 Lead Developer & Systems Architect</small></div>"
                "<div class='team-card'><b style='color:#2ecc71;'>Prami Hazra & Sanchari Choudhury</b><br><small>📝 Documentation & Reports</small></div>"
                "<div class='team-card'><b style='color:#e67e22;'>Mainak Mukherjee & Manas Banerjee</b><br><small>📊 System Evaluation Arrays</small></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("<div class='history-title'>Recent Chats</div>", unsafe_allow_html=True)
    recent_prompts = get_unique_user_prompts()
    
    if recent_prompts:
        for prompt_heading in recent_prompts:
            if st.button(f"💬 {prompt_heading}", key=f"hist_{prompt_heading}", use_container_width=True):
                st.session_state.active_display = prompt_heading
                st.session_state.active_payload = prompt_heading
                st.rerun()
                
    st.markdown("---")
    st.subheader("🛠️ Memory Management")
    
    history_compiled_text = "\n".join([f"### {m['role'].upper()}:\n{m['content']}\n" for m in st.session_state.chat_history])
    st.download_button("📥 Export Active Session Log (.md)", data=history_compiled_text, file_name="session_report.md", use_container_width=True)
    
    if st.button("🗑️ Clear History Logs", use_container_width=True):
        clear_database()
        st.session_state.chat_history = []
        st.session_state.active_payload = ""
        st.session_state.active_display = ""
        st.rerun()
    
    st.markdown("---")
    st.subheader("🧠 Thought Stream Tracing")
    cfg_verbose = st.checkbox("💡 Show Live Telemetry Debugger", value=True)
    st.caption(f"🔋 System RAM Footprint: {sys.getsizeof(st.session_state.chat_history)} Bytes")
    
    log_placeholder = st.empty()
    log_placeholder.info("System idle.")

    if st.button("🚪 Log Out of Session", use_container_width=True):
        st.session_state.login_authenticated = False
        st.rerun()

# --- MAIN CHAT PANEL FRAMEWORK ---
st.title("⚡ Offline Smart Agentic Workspace")
st.caption(f"⚡ Core Computation Velocity Node: `{st.session_state.speed_telemetry}`")

# Display conversation logs
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Quick Access Shortcut Pills
pill_count = 3 if st.session_state.is_online else 2
pill_cols = st.columns(pill_count)
with pill_cols[0]:
    if st.button("🔍 Auditing Error Logs", use_container_width=True): st.session_state.gemini_text_box = "Explain structural error parameters in this file context:"; st.rerun()
with pill_cols[1]:
    if st.button("📊 Step-by-Step Math Solving", use_container_width=True): st.session_state.gemini_text_box = "Solve this complex mathematical equation step-by-step:"; st.rerun()
if st.session_state.is_online:
    with pill_cols[2]:
        if st.button("📰 Daily Live News Bulletins", use_container_width=True): st.session_state.gemini_text_box = "Give me international live current affairs updates"; st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# Form entry callback handler
def handle_submission_callback():
    raw_text = st.session_state.gemini_text_box.strip()
    if raw_text:
        st.session_state.active_display = raw_text
        st.session_state.active_payload = raw_text
        st.session_state.gemini_text_box = ""

# =====================================================================
#  📌 THE RESTRUCTURED HORIZONTAL BUTTON MATRIX 
# =====================================================================
file_payload_string = ""
voice_text_transcription = None

# Custom Flex Wrapper using Native Grid Elements to ensure clean horizontal side-by-side alignment
col_file, col_mic, col_spacer = st.columns([3.8, 0.8, 7.4])

with col_file:
    st.markdown("<div class='custom-upload-box'>📂 <b style='color: var(--text-color);'>Upload Context</b>", unsafe_allow_html=True)
    uploaded_doc = st.file_uploader("Upload", type=["txt", "json", "c", "py", "html", "csv"], key="gemini_file_node")
    if uploaded_doc is not None:
        try:
            file_raw = uploaded_doc.read().decode("utf-8", errors="ignore")
            file_payload_string = f"\n\n[SYSTEM ATTACHED FILE CONTEXT DETAILS:\nFilename: {uploaded_doc.name}\nContent:\n{file_raw}\n]"
        except Exception as e:
            st.error(f"Err: {str(e)}")
    st.markdown("</div>", unsafe_allow_html=True)

with col_mic:
    st.markdown("<div class='custom-mic-box'>", unsafe_allow_html=True)
    voice_text_transcription = speech_to_text(start_prompt="🎙️", stop_prompt="⏹️", language="en", just_once=True, key="gemini_mic_stream")
    if voice_text_transcription:
        st.session_state.active_display = voice_text_transcription
        st.session_state.active_payload = voice_text_transcription
    st.markdown("</div>", unsafe_allow_html=True)

# Main Action Input Form Bar (Positioned cleanly below the attachment layout blocks)
with st.form("multimodal_prompt_form", clear_on_submit=True):
    st.markdown("<div class='premium-prompt-bar'>", unsafe_allow_html=True)
    col_text_field, col_submit_rocket = st.columns([12, 0.8])
    
    with col_text_field:
        text_input_query = st.text_input("Prompt Box Field", placeholder="Ask Offline.Ai or utilize speech/document layers...", label_visibility="collapsed", key="gemini_text_box")
        
    with col_submit_rocket:
        submit_triggered = st.form_submit_button("🚀", on_click=handle_submission_callback, use_container_width=True)
        
    st.markdown("</div>", unsafe_allow_html=True)

if file_payload_string and st.session_state.active_payload:
    if not st.session_state.active_payload.endswith(file_payload_string):
        st.session_state.active_payload += file_payload_string

# =====================================================================
#  4. LIVE AGENT THINKING LOOP CONTROLLER
# =====================================================================
if st.session_state.active_display:
    display_user_query = st.session_state.active_display
    final_query_payload = st.session_state.active_payload
    
    st.session_state.active_display = ""
    st.session_state.active_payload = ""
    
    with st.chat_message("user"):
        st.markdown(display_user_query)
    
    st.session_state.chat_history.append({"role": "user", "content": display_user_query})
    save_message("user", display_user_query)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_placeholder.markdown("⏳ *Accessing intelligence matrix...*")
        
        system_rules = f"""
You are a premium hybrid AI agent operating smoothly in both online and offline network frames.
Your name is 'Offline.Ai', developed by Mrinal Gorain, a student of Nalhati Government Polytechnic, Branch of CST.

PROJECT DOCUMENTATION CREDIT DIRECTIVE:
- The project documentation and report creation were entirely designed and created by Prami Hazra and Sanchari Choudhury.

REQUIRED REINFORCED PERSONA STYLE TONE MATRIX:
- Current active persona setting to maintain: {cfg_tone}

CRITICAL MATHEMATICAL LATEX GUARDRAILS:
- You can solve any complex engineering mathematics step-by-step.
- Use $inline$ markers for equations within running text sentences.
- Use $$display$$ markers for major standalone equations or derivations.

CRITICAL MULTILINGUAL LANGUAGE MATRIX DIRECTIVE:
- You understand English, Hindi, Bengali, Hinglish, and Benglish.
  1. If the user asks a question in Bengali OR romanized Benglish text, translate and reply 100% inside pure BENGALI SCRIPT (বাংলা হরফ) only.
  2. If the user asks a question in Hindi OR romanized Hinglish text, translate and reply 100% inside pure HINDI SCRIPT (देवनागरी) only.
  3. If the user asks in standard English, reply in standard English.

CURRENT NETWORK STATE STATUS:
- System is currently executing inside an {'ONLINE' if st.session_state.is_online else 'OFFLINE'} environment.
"""
        if st.session_state.is_online:
            system_rules += """
Tools Directory (Active only when Online):
1. Weather queries: {"tool": "get_live_weather", "argument": "CITY_NAME"}
2. General topic news: {"tool": "get_world_news", "argument": "TOPIC_KEYWORDS"}
3. Specific Factual Search: {"tool": "query_live_search", "argument": "SEARCH_KEYWORDS"}

If the request requires live data parameters, you MUST output a tool calling using valid JSON formatting.
"""
        else:
            system_rules += "\nSystem is offline. Solve all math and logical data queries natively via local weights."

        agent_context = [{"role": "system", "content": system_rules}]
        for past_msg in st.session_state.chat_history[-4:]:
            agent_context.append({"role": past_msg["role"], "content": past_msg["content"]})
            
        if file_payload_string:
            agent_context.append({"role": "user", "content": final_query_payload})

        running_logs = ""
        tool_executed = False
        final_text_output = ""
        
        if st.session_state.is_online:
            for processing_step in range(2):
                llm_response = client.chat(
                    model="llama3", 
                    messages=agent_context,
                    options={"temperature": 0.1, "num_predict": 100, "top_k": 20, "num_thread": 4}
                )
                raw_content = llm_response['message']['content'].strip()
                try:
                    tool_call = json.loads(raw_content)
                    if "tool" in tool_call and tool_call["tool"] in tools_map:
                        t_name = tool_call["tool"]
                        t_arg = tool_call["argument"]
                        if cfg_verbose:
                            running_logs += f"🔍 **Step {processing_step+1}: Thought Trace**\nAI deployed tool `{t_name}` for `{t_arg}`.\n\n"
                            log_placeholder.markdown(f"<div class='log-card'>{running_logs}</div>", unsafe_allow_html=True)
                        final_text_output = tools_map[t_name](t_arg)
                        tool_executed = True
                        if cfg_verbose:
                            running_logs += f"📡 **Data Returned Successfully.**\n\n"
                            log_placeholder.markdown(f"<div class='log-card'>{running_logs}</div>", unsafe_allow_html=True)
                        break
                except json.JSONDecodeError:
                    break
            
            if not tool_executed:
                user_query_clean = display_user_query.lower()
                if any(w_kwd in user_query_clean for w_kwd in ["weather", "temperature", "temp", "rain", "humidity"]):
                    if cfg_verbose:
                        running_logs += f"🚨 **System Intercept:** Meteorological intent verified.\n\n"
                        log_placeholder.markdown(f"<div class='log-card'>{running_logs}</div>", unsafe_allow_html=True)
                    city_target = "Nalhati"
                    for word in display_user_query.split():
                        clean_word = word.strip("?,.!")
                        if clean_word.title() not in ["Live", "Weather", "Report", "Of", "In", "What", "Is"]:
                            city_target = clean_word
                            break
                    final_text_output = get_live_weather(city_target)
                    tool_executed = True
                elif any(f_kwd in user_query_clean for f_kwd in ["cm", "news", "minister", "current affairs"]):
                    if cfg_verbose:
                        running_logs += f"🚨 **System Intercept:** Triggering web index scan...\n\n"
                        log_placeholder.markdown(f"<div class='log-card'>{running_logs}</div>", unsafe_allow_html=True)
                    final_text_output = query_live_search(display_user_query)
                    tool_executed = True

        if tool_executed:
            st.session_state.chat_history.append({"role": "assistant", "content": final_text_output})
            save_message("assistant", final_text_output)
            st.rerun()
        else:
            start_time = time.time()
            stats_tracker = [0]
            
            def text_stream_generator():
                stream_res = client.chat(
                    model="llama3", 
                    messages=agent_context, 
                    stream=True,
                    options={"temperature": 0.1, "num_thread": 4}
                )
                for chunk in stream_res:
                    stats_tracker[0] += 1
                    yield chunk['message']['content']

            full_response = response_placeholder.write_stream(text_stream_generator())
            elapsed_time = time.time() - start_time
            if elapsed_time > 0:
                st.session_state.speed_telemetry = f"{round(stats_tracker[0] / elapsed_time, 1)} tokens/sec"
                
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})
            save_message("assistant", full_response)

        st.components.v1.html("""
            <script>
                var chatWindow = window.parent.document.querySelector('.main');
                if (chatWindow) { chatWindow.scrollTo({ top: chatWindow.scrollHeight, behavior: 'smooth' }); }
            </script>
        """, height=0)
        st.rerun()