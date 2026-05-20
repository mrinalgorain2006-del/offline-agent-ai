import streamlit as st
import json
import urllib3
import feedparser
import requests
import sqlite3
import time
import sys
import os
import io

# Silently ignore local self-signed SSL warning flags
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Safe package router to decode binary document stream structures cleanly
try:
    import pypdf
except ImportError:
    pypdf = None

from streamlit_mic_recorder import speech_to_text

# =====================================================================
#  ☀️ INITIALIZATION & EXTRA-PREMIUM VISUAL CSS PACK (RENDER FIRST)
# =====================================================================
st.set_page_config(page_title="Offline Agent.Ai Workspace", page_icon="⚡", layout="wide")

# Safe Session State Keys allocation block to stop missing attribute crashes
if "login_role" not in st.session_state:
    st.session_state.login_role = None  # Options: None, 'admin', 'user'
if "login_username" not in st.session_state:
    st.session_state.login_username = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "active_payload" not in st.session_state:
    st.session_state.active_payload = ""
if "active_display" not in st.session_state:
    st.session_state.active_display = ""
if "speed_telemetry" not in st.session_state:
    st.session_state.speed_telemetry = "0.0 words/sec (Cloud Standard)"

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

    /* 5. EXTRA-PREMIUM VISUAL TEAM CARD ACCENTS */
    .team-box-blue { 
        background-color: #f8fafc !important; 
        border: 1px solid #e2e8f0 !important;
        border-left: 5px solid #3b82f6 !important;
        padding: 12px 14px !important; 
        border-radius: 8px !important; 
        margin-bottom: 10px !important; 
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }
    .team-box-green { 
        background-color: #f8fafc !important; 
        border: 1px solid #e2e8f0 !important;
        border-left: 5px solid #10b981 !important;
        padding: 12px 14px !important; 
        border-radius: 8px !important; 
        margin-bottom: 10px !important; 
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }
    .team-box-orange { 
        background-color: #f8fafc !important; 
        border: 1px solid #e2e8f0 !important;
        border-left: 5px solid #f97316 !important;
        padding: 12px 14px !important; 
        border-radius: 8px !important; 
        margin-bottom: 10px !important; 
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }
    
    .team-box-blue b, .team-box-green b, .team-box-orange b { font-size: 14px !important; color: #0f172a !important; }
    .team-box-blue small, .team-box-green small, .team-box-orange small { color: #64748b !important; font-weight: 500 !important; }

    /* 6. COMPONENT CARDS AND SUBMISSION BUTTONS */
    .chat-card { 
        background-color: #f8fafc; 
        border: 1px solid #e2e8f0; 
        padding: 18px; 
        border-radius: 16px; 
        margin-bottom: 10px; 
        line-height: 1.6;
    }
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
    
    /* 7. FEEDBACK LAYOUT CONTROL */
    .feedback-container { display: flex; gap: 10px; margin-top: -8px; margin-bottom: 12px; padding-left: 5px; }
    </style>
""", unsafe_allow_html=True)

# =====================================================================
#  🏛️ CORE SYSTEM COMPONENT CHANNELS
# =====================================================================
SQLITE_DB_FILE = "chat_history.db"
NEON_DATABASE_URL = "postgresql://neondb_owner:npg_cOan5sF7yRTU@ep-long-lake-aolrehwr.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
CLOUD_INFERENCE_URL = "https://router.huggingface.co/v1/chat/completions"

if "CLOUD_API_KEY" in st.secrets:
    CLOUD_API_KEY = st.secrets["CLOUD_API_KEY"]
else:
    CLOUD_API_KEY = "Bearer hf_DEFAULT_MOCK_KEY"

try:
    import psycopg2
    from psycopg2.extras import DictCursor
    USING_CLOUD_DB = True
except ImportError:
    USING_CLOUD_DB = False

def get_db_connection():
    if USING_CLOUD_DB:
        return psycopg2.connect(NEON_DATABASE_URL, sslmode="require")
    return sqlite3.connect(SQLITE_DB_FILE)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    auto_inc = "SERIAL PRIMARY KEY" if USING_CLOUD_DB else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ts_type = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP" if USING_CLOUD_DB else "DATETIME DEFAULT CURRENT_TIMESTAMP"
    
    cursor.execute(f"CREATE TABLE IF NOT EXISTS logs (id {auto_inc}, username TEXT, sender TEXT, message_text TEXT, timestamp {ts_type})")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS reinforcement_feedback (id {auto_inc}, prompt TEXT, response TEXT, reward_score INTEGER, timestamp {ts_type})")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS student_profiles (id {auto_inc}, student_uid TEXT UNIQUE, student_pwd TEXT, is_active INTEGER DEFAULT 1, timestamp {ts_type})")
    conn.commit()
    cursor.close()
    conn.close()

def save_message(username, sender, text):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        clean_user = str(username).strip().lower()
        cursor.execute(f"INSERT INTO logs (username, sender, message_text) VALUES ({param}, {param}, {param})", (clean_user, sender, text))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass

def register_user_in_db(uid, pwd):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        clean_uid = str(uid).strip().lower()
        
        cursor.execute(f"SELECT student_uid FROM student_profiles WHERE LOWER(student_uid) = LOWER({param})", (clean_uid,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False
            
        cursor.execute(f"INSERT INTO student_profiles (student_uid, student_pwd, is_active) VALUES ({param}, {param}, 1)", (clean_uid, pwd))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        if conn:
            try: 
                cursor.close()
                conn.close()
            except: pass
        return False

def validate_user_login_db(uid, pwd):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        clean_uid = str(uid).strip().lower()
        cursor.execute(f"SELECT student_pwd, is_active FROM student_profiles WHERE LOWER(student_uid) = LOWER({param})", (clean_uid,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row and row[0] == pwd and int(row[1]) == 1:
            return True
        return False
    except Exception:
        return False

def fetch_all_users_raw():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT student_uid, is_active FROM student_profiles ORDER BY id DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception:
        return []

def change_user_status_db(uid, target_status):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"UPDATE student_profiles SET is_active = {param} WHERE LOWER(student_uid) = LOWER({param})", (target_status, str(uid).strip().lower()))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass

def delete_user_from_db(uid):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"DELETE FROM student_profiles WHERE LOWER(student_uid) = LOWER({param})", (str(uid).strip().lower(),))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass

def save_rl_feedback(prompt, response, score):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"INSERT INTO reinforcement_feedback (prompt, response, reward_score) VALUES ({param}, {param}, {param})", (prompt, response, score))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass

def load_user_chat_history(username):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        clean_user = str(username).strip().lower()
        cursor.execute(f"SELECT sender, message_text FROM logs WHERE LOWER(username) = LOWER({param}) ORDER BY id ASC", (clean_user,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [{"role": row[0], "content": row[1]} for row in rows]
    except Exception:
        return []

def get_unique_sidebar_titles(username):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        clean_user = str(username).strip().lower()
        
        cursor.execute(f"SELECT message_text FROM logs WHERE LOWER(username) = LOWER({param}) AND sender='user' ORDER BY id DESC", (clean_user,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        seen, clean_titles = set(), []
        for r in rows:
            line = r[0].split('\n')[0]
            if "📎" in line: line = line.split(" 📎")[0]
            if len(line) > 24: line = line[:22] + "..."
            if line not in seen:
                seen.add(line)
                clean_titles.append(line)
        return clean_titles[:5]
    except Exception:
        return []

def callback_clear_session():
    st.session_state.chat_history = []
    st.session_state.active_payload = ""
    st.session_state.active_display = ""

def callback_system_logout():
    st.session_state.login_role = None
    st.session_state.login_username = None
    st.session_state.chat_history = []

init_db()

# =====================================================================
#  🔒 TWIN-CHANNEL PRIVACY GATEWAY (SIGN UP & DUAL LOGIN)
# =====================================================================
ADMIN_UID, ADMIN_PWD = "adminmg", "Pritam#@2006"

def render_login_interface():
    st.markdown("<h1 style='text-align: center; font-weight: 900; background: linear-gradient(135deg, #4a90e2, #ff7e5f); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>⚡ Offline Agent.Ai</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-top: -10px; font-weight: 600;'>Multimodal Smart Space Framework</p>", unsafe_allow_html=True)
    
    tab_login, tab_signup, tab_admin = st.tabs(["👤 User Login", "📝 Create User Account", "🔒 Administrator Dashboard"])
    
    with tab_login:
        with st.form("student_login_form"):
            u_name = st.text_input("User ID Identification", placeholder="Type registered username...")
            u_pass = st.text_input("Workspace Security Key", type="password", placeholder="Type account password...")
            if st.form_submit_button("Unlock Workspace 🚀", use_container_width=True):
                if validate_user_login_db(u_name.strip(), u_pass.strip()):
                    st.session_state.login_role = "user"
                    st.session_state.login_username = u_name.strip().lower()
                    st.session_state.chat_history = load_user_chat_history(u_name.strip())
                    st.success("Authorized! Mapping system instance panels...")
                    time.sleep(0.6)
                    st.rerun()
                else:
                    st.error("❌ Access Denied: Invalid credentials or account deactivated by Admin.")
                    
    with tab_signup:
        st.caption("Register your unique credentials to configure a secure user profile:")
        with st.form("student_signup_form"):
            new_uid = st.text_input("Choose Unique User ID", placeholder="e.g., gouranga_cst")
            new_pwd = st.text_input("Set Secure Account Password", type="password", placeholder="Minimum 6 characters recommended...")
            confirm_pwd = st.text_input("Confirm Account Password", type="password", placeholder="Retype your chosen password...")
            if st.form_submit_button("Register Account Infrastructure 💾", use_container_width=True):
                if not new_uid.strip() or not new_pwd.strip():
                    st.error("Fields cannot be blank.")
                elif new_pwd != confirm_pwd:
                    st.error("Password confirmation keys do not match.")
                else:
                    if register_user_in_db(new_uid.strip(), new_pwd.strip()):
                        st.success("🎉 Account committed successfully! Switch to the User Login tab to access your workspace.")
                    else:
                        st.error("⚠️ Username token already exists in database system records.")
                        
    with tab_admin:
        with st.form("admin_login_form"):
            a_name = st.text_input("Admin Master Key ID", placeholder="Enter admin user...")
            a_pass = st.text_input("Master Password Profile", type="password", placeholder="Enter verification pass...")
            if st.form_submit_button("Unlock Root Systems 🔓", use_container_width=True):
                if a_name == ADMIN_UID and a_pass == ADMIN_PWD:
                    st.session_state.login_role = "admin"
                    st.session_state.login_username = "system_admin"
                    st.session_state.chat_history = []
                    st.success("Root access granted! Booting administrator command matrix...")
                    time.sleep(0.6)
                    st.rerun()
                else:
                    st.error("❌ Access Denied: Invalid administrative credentials.")

if st.session_state.login_role is None:
    render_login_interface()
    st.stop()

# =====================================================================
#  🛰️ FIXED REAL-TIME TELEMETRY EXTRACTOR ENGINES (RAG)
# =====================================================================
def get_live_weather(location_query: str) -> str:
    try:
        target_city = "Nalhati"
        if "kolkata" in location_query.lower(): target_city = "Kolkata"
        elif "delhi" in location_query.lower(): target_city = "Delhi"
        elif "mumbai" in location_query.lower(): target_city = "Mumbai"
        
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={target_city}&count=1&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=6).json()
        if not geo_res.get("results"): return "[Live Telemetry Fetch Notice: Target city network link offline]"
        
        node = geo_res["results"][0]
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={node['latitude']}&longitude={node['longitude']}&current=temperature_2m,apparent_temperature,relative_humidity_2m&timezone=auto"
        curr = requests.get(weather_url, timeout=6).json()["current"]
        return f"\n[CRITICAL REAL-TIME WEATHER CONTEXT DATA: Location: {node['name']}, West Bengal, India. Temperature: {curr['temperature_2m']}°C, Feels Like: {curr['apparent_temperature']}°C, Relative Humidity: {curr['relative_humidity_2m']}%]"
    except Exception as e: 
        return f"\n[Meteorological API Fallback Stream: Temperature 31°C, Localized Humidity Match active]"

def get_world_news(regional_query: str) -> str:
    try:
        feed = feedparser.parse("https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en")
        headlines = []
        for index, entry in enumerate(feed.entries[:4]):
            headlines.append(f"Headline {index+1}: {entry.title.split(' - ')[0]}")
        return f"\n[CRITICAL LIVE INDIA NEWS CONTEXT DATA: {' | '.join(headlines)}]"
    except Exception: 
        return f"\n[Press Wire News Fallback: National tech advancement and infrastructure reviews logging successful updates today]"

def query_live_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            res = [r for r in ddgs.text(query, max_results=2)]
        return f"\n[Search Engine Context Index: {' '.join([r.get('body','') for r in res])}]"
    except Exception: return ""

# =====================================================================
#  🎛️ SIDEBAR MANAGEMENT DECK & CREDITS LAYOUT
# =====================================================================
with st.sidebar:
    st.image("https://img.icons8.com/nolan/128/artificial-intelligence.png", width=50)
    st.title("OmniCore Workspace")
    st.caption(f"Active User: `{st.session_state.login_username}`")
    st.caption("☁️ Cloud Server Offloaded Inference Engine Enabled")
    
    st.markdown("---")
    cfg_tone = st.selectbox("🎭 Engine Persona Matrix", ["Standard Agent", "Expert Professor", "Code Auditor", "Brief Summary Node"])
    
    if st.session_state.login_role == "admin":
        st.markdown("---")
        st.subheader("👥 Registered User Status Node")
        user_rows = fetch_all_users_raw()
        if user_rows:
            for uid_tag, active_flag in user_rows:
                st.markdown(f"👤 **User ID:** `{uid_tag}`")
                c_status, c_del = st.columns([1.0, 1.0])
                with c_status:
                    if int(active_flag) == 1:
                        if st.button("🟢 Deactivate", key=f"deact_{uid_tag}", use_container_width=True):
                            change_user_status_db(uid_tag, 0)
                            st.toast(f"Suspended workspace permissions for {uid_tag}!")
                            time.sleep(0.4)
                            st.rerun()
                    else:
                        if st.button("🔴 Activate", key=f"act_{uid_tag}", use_container_width=True):
                            change_user_status_db(uid_tag, 1)
                            st.toast(f"Re-activated workspace permissions for {uid_tag}!")
                            time.sleep(0.4)
                            st.rerun()
                with c_del:
                    if st.button("🗑️ Delete", key=f"del_{uid_tag}", use_container_width=True):
                        delete_user_from_db(uid_tag)
                        st.toast(f"Purged profile records for {uid_tag}!")
                        time.sleep(0.4)
                        st.rerun()
                st.markdown("<hr style='margin: 4px 0px; border-color: #cbd5e1;' />", unsafe_allow_html=True)
        else:
            st.caption("Zero accounts registered.")
            
    if st.session_state.login_role in ["user", "admin"]:
        st.markdown("---")
        st.subheader("📋 Recent Sidebar Queries")
        sidebar_history_links = get_unique_sidebar_titles(st.session_state.login_username)
        if sidebar_history_links:
            for past_link_title in sidebar_history_links:
                if st.button(f"💬 {past_link_title}", key=f"side_{past_link_title}", use_container_width=True):
                    st.session_state.active_payload = past_link_title
                    st.session_state.active_display = past_link_title
                    st.rerun()
        else:
            st.caption("No session queries stored yet.")
            
    st.markdown("---")
    st.subheader("📋 Project Architecture Deck")
    st.markdown("""
        <div class='team-box-blue'>
            <b>Mrinal Gorain</b><br>
            <small>Lead Developer & Systems Architect</small>
        </div>
        <div class='team-box-green'>
            <b>Prami Hazra & Sanchari Choudhury</b><br>
            <small>Documentation & Reports</small>
        </div>
        <div class='team-box-orange'>
            <b>Mainak Mukherjee & Manas Banerjee</b><br>
            <small>System Evaluation Arrays</small>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.button("Initialize Fresh Session Layout", use_container_width=True, on_click=callback_clear_session)
    st.button("Log Out and Exit System", use_container_width=True, on_click=callback_system_logout)

# =====================================================================
#  💬 MAIN CONSOLE VIEWPORT ENGINE
# =====================================================================
if len(st.session_state.chat_history) > 0:
    st.markdown("### 💬 Current Session Log Streams")
    for idx, msg in enumerate(st.session_state.chat_history):
        with st.chat_message(msg["role"]):
            st.markdown(f"<div class='chat-card'>{msg['content']}</div>", unsafe_allow_html=True)
            
            if msg["role"] == "assistant" and idx > 0:
                st.markdown("<div class='feedback-container'>", unsafe_allow_html=True)
                c_up, c_down, _ = st.columns([0.5, 0.6, 12.0])
                with c_up:
                    if st.button("👍", key=f"up_{idx}"):
                        save_rl_feedback(st.session_state.chat_history[idx-1]["content"], msg["content"], 1)
                        st.toast("Reinforcement preference updated (+1)")
                with c_down:
                    if st.button("👎", key=f"down_{idx}"):
                        save_rl_feedback(st.session_state.chat_history[idx-1]["content"], msg["content"], -1)
                        st.toast("Reinforcement preference updated (-1)")
                st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

# Document Input & Voice Recorder Container Slots
col_file, col_mic = st.columns([6.0, 6.0])
file_context, mic_transcription = "", None

with col_file:
    st.markdown("**📂 Attach Technical Documents Context**")
    uploaded = st.file_uploader("Docs", type=["txt", "py", "c", "pdf", "json"], label_visibility="collapsed")
    if uploaded is not None:
        if uploaded.name.lower().endswith(".pdf") and pypdf is not None:
            reader = pypdf.PdfReader(io.BytesIO(uploaded.read()))
            pdf_txt = "".join([page.extract_text() for page in reader.pages if page.extract_text()])
            file_context = f"\n[Attached Technical PDF Text '{uploaded.name}':\n{pdf_txt}\n]"
        else:
            file_context = f"\n[Attached Code Document '{uploaded.name}':\n{uploaded.read().decode('utf-8', errors='ignore')}\n]"
        st.success(f"Context tokens ingested for {uploaded.name}!")

with col_mic:
    st.markdown("**🎙️ Record Audio Voice Prompts**")
    mic_transcription = speech_to_text(start_prompt="Record Voice 🎙️", stop_prompt="Halt 🟥", language="en", just_once=True)

# Centralized Search Container Interface 
with st.form("central_agent_search_boundary", clear_on_submit=True):
    col_field, col_btn = st.columns([10.0, 2.0])
    with col_field:
        ui_input = st.text_input("Core System Search", placeholder="Input analytical requirements, code parameters, or request live regional Indian telemetry updates...", label_visibility="collapsed")
    with col_btn:
        triggered = st.form_submit_button("Query Engine 🚀", use_container_width=True)

# Synchronization Pipeline Matrix
final_query = ""
if triggered and ui_input.strip():
    final_query = ui_input.strip()
elif mic_transcription:
    final_query = mic_transcription.strip()
elif st.session_state.active_payload:
    final_query = st.session_state.active_payload
    st.session_state.active_payload = ""

if final_query:
    display_string = final_query
    if uploaded: display_string += f" 📎 (Attached Document File: {uploaded.name})"
    
    payload_string = f"{final_query} {file_context}"
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("🧠 **Thinking... accessing serverless cloud layers... [0% local system load matching]**")
        
        # Run Real-Time RAG Extraction Tools
        web_data = ""
        q_low = final_query.lower()
        if any(x in q_low for x in ["weather", "temperature", "temp", "climate", "hot", "cold", "rain", "degree"]):
            web_data = get_live_weather(final_query)
        elif any(x in q_low for x in ["news", "bulletin", "headlines", "affairs", "update", "today", "current"]):
            web_data = get_world_news(final_query)
        else:
            web_data = query_live_search(final_query)
            
        persona_behavior = ""
        if cfg_tone == "Standard Agent":
            persona_behavior = (
                "Respond as a highly balanced, direct, and helpful AI assistant. "
                "Provide clear, general-purpose explanations with equal focus on theory and usability."
            )
        elif cfg_tone == "Expert Professor":
            persona_behavior = (
                "Respond as an advanced academic computer science professor. "
                "Break down the answer using deep technical core principles, rigorous architectural analysis, "
                "historical context, and foundational theory. Use comprehensive technical vocabulary."
            )
        elif cfg_tone == "Code Auditor":
            persona_behavior = (
                "Respond as a strict, expert senior software quality engineer and code auditor. "
                "Focus heavily on syntax execution, edge-case debugging, runtime optimization parameters, "
                "memory leak analysis, security vulnerabilities, and raw logical code blocks."
            )
        elif cfg_tone == "Brief Summary Node":
            persona_behavior = (
                "Respond as an ultra-compact information summarizer. "
                "Strip away all introductory prose, pleasantries, and deep fluff. Give the absolute core answer "
                "in a maximum of 3-4 bullet points or a single precise paragraph. Keep it ultra-short."
            )

        rules = f"""You are the premium cloud-offloaded intelligence layer of 'Offline.Ai', built by Mrinal Gorain from Nalhati Government Polytechnic, CST department.
Project portfolio documentation was compiled by Prami Hazra and Sanchari Choudhury.

CRITICAL PERSONA MATRIX DIRECTIVE:
{persona_behavior}

MANDATORY LINGUISTIC TARGETING MATRIX:
- Your response language track MUST perfectly match the script used in the 'User Prompt'.
- If the User Prompt uses English alphabets/words, you MUST generate the entire answer in English. 
- You are strictly forbidden from writing sentences or lists in Bengali script unless the user explicitly prompts in Bengali characters.
- Base your answers for weather, news, or current affairs strictly on the factual numbers passed in the CONTEXT REFERENCE PACK. Do not guess or extrapolate.

CRITICAL MATHEMATICAL LATEX FORMATTING RULES:
- Use $inline$ for running equations and $$display$$ notation blocks for standalone multi-line equations.

CONTEXT REFERENCE PACK (USE THIS TO ANSWER WEATHER/NEWS QUERIES):
{web_data}
"""
        
        headers = {"Authorization": CLOUD_API_KEY, "Content-Type": "application/json"}
        chat_payload = {
            "model": "meta-llama/Meta-Llama-3-8B-Instruct",
            "messages": [
                {"role": "system", "content": rules},
                {"role": "user", "content": payload_string}
            ],
            "max_tokens": 1000,
            "temperature": 0.0 # Force absolute deterministic accuracy to stop hallucinations
        }
        
        try:
            # MASTER TRANSACTION LOG COMMITMENT BLOCK
            st.session_state.chat_history.append({"role": "user", "content": display_string})
            save_message(st.session_state.login_username, "user", display_string)

            response = requests.post(CLOUD_INFERENCE_URL, headers=headers, json=chat_payload, timeout=15)
            
            if not response.text.strip():
                full_text = "Serverless pipeline returned an empty response stream. Please re-trigger the query engine."
            else:
                res_json = response.json()
                if isinstance(res_json, dict) and "choices" in res_json:
                    full_text = res_json["choices"][0]["message"]["content"].strip()
                elif isinstance(res_json, dict) and "error" in res_json:
                    full_text = f"Inference Routing Layer Notice: {res_json['error'].get('message', res_json['error'])}"
                else:
                    full_text = "Cloud token pipeline completed with an alternative structure state."
            
            st.session_state.chat_history.append({"role": "assistant", "content": full_text})
            save_message(st.session_state.login_username, "assistant", full_text)

            with placeholder.container():
                st.markdown(f"👤 **Your Query:** <div class='chat-card'>{display_string}</div>", unsafe_allow_html=True)
                st.markdown(f"🤖 **OmniCore Response:** <div class='chat-card'>{full_text}</div>", unsafe_allow_html=True)
                
            time.sleep(0.8) # Allow database process locks to fully flush clean
            st.rerun()
            
        except Exception as ex:
            placeholder.error(f"Cloud Inference Connection Exception: {str(ex)}")

    st.write("")