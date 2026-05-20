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
    .chat-card { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; border-radius: 16px; margin-bottom: 10px; }
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

# =====================================================================
#  1. CLOUD STORAGE ROUTER & PERSISTENT DATA SCHEMA (NEON ENVIRONMENT)
# =====================================================================
SQLITE_DB_FILE = "chat_history.db"
NEON_DATABASE_URL = "postgresql://neondb_owner:npg_cOan5sF7yRTU@ep-long-lake-aolrehwr.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# Serverless Cloud Inference Configuration Layer
CLOUD_INFERENCE_URL = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct"
#  NEW SECURE CONFIGURATION
if "CLOUD_API_KEY" in st.secrets:
    CLOUD_API_KEY = st.secrets["CLOUD_API_KEY"]
else:
    CLOUD_API_KEY = "Bearer hf_DEFAULT_MOCK_KEY"  # Fallback
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
    conn.close()

def save_message(username, sender, text):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"INSERT INTO logs (username, sender, message_text) VALUES ({param}, {param}, {param})", (username, sender, text))
        conn.commit()
        conn.close()
    except Exception:
        pass

def register_user_in_db(uid, pwd):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"INSERT INTO student_profiles (student_uid, student_pwd, is_active) VALUES ({param}, {param}, 1)", (uid, pwd))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def validate_user_login_db(uid, pwd):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"SELECT student_pwd, is_active FROM student_profiles WHERE student_uid = {param}", (uid,))
        row = cursor.fetchone()
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
        conn.close()
        return rows
    except Exception:
        return []

def change_user_status_db(uid, target_status):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"UPDATE student_profiles SET is_active = {param} WHERE student_uid = {param}", (target_status, uid))
        conn.commit()
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
        conn.close()
    except Exception:
        pass

def load_user_chat_history(username):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"SELECT sender, message_text FROM logs WHERE username = {param} ORDER BY id ASC", (username,))
        rows = cursor.fetchall()
        conn.close()
        return [{"role": row[0], "content": row[1]} for row in rows]
    except Exception:
        return []

def get_unique_sidebar_titles(username):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"SELECT message_text FROM logs WHERE username = {param} AND sender='user' ORDER BY id DESC", (username,))
        rows = cursor.fetchall()
        conn.close()
        seen, clean_titles = set(), []
        for r in rows:
            line = r[0].split('\n')[0]
            if "📎" in line: line = line.split(" 📎")[0]
            if "📷" in line: line = line.split(" 📷")[0]
            if len(line) > 24: line = line[:22] + "..."
            if line not in seen:
                seen.add(line)
                clean_titles.append(line)
        return clean_titles[:5]
    except Exception:
        return []

init_db()

# Establish Online State Tracker
try:
    requests.get("https://1.1.1.1", timeout=2)
    st.session_state.is_online = True
except Exception:
    st.session_state.is_online = False

# =====================================================================
#  🔒 TWIN-CHANNEL PRIVACY GATEWAY (REQUIREMENT 2: SIGN UP & DUAL LOGIN)
# =====================================================================
ADMIN_UID, ADMIN_PWD = "adminmg", "Pritam#@2006"

def render_login_interface():
    st.markdown("<h1 style='text-align: center; font-weight: 900; background: linear-gradient(135deg, #4a90e2, #ff7e5f); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>⚡ Offline Agent.Ai</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-top: -10px; font-weight: 600;'>Multimodal Smart Space Framework</p>", unsafe_allow_html=True)
    
    tab_login, tab_signup, tab_admin = st.tabs(["👤 Student Login", "📝 Create Student Account", "🔒 Administrator Dashboard"])
    
    with tab_login:
        with st.form("student_login_form"):
            u_name = st.text_input("Student User ID Identification", placeholder="Type registered username...")
            u_pass = st.text_input("Workspace Security Key", type="password", placeholder="Type account password...")
            if st.form_submit_button("Unlock Workspace 🚀", use_container_width=True):
                if validate_user_login_db(u_name.strip(), u_pass.strip()):
                    st.session_state.login_role = "user"
                    st.session_state.login_username = u_name.strip()
                    st.session_state.chat_history = load_user_chat_history(u_name.strip())
                    st.success("Authorized! Mapping student instance panels...")
                    time.sleep(0.6)
                    st.rerun()
                else:
                    st.error("❌ Access Denied: Invalid credentials or account deactivated by Admin.")
                    
    with tab_signup:
        st.caption("Register your unique credentials to configure a secure student profile:")
        with st.form("student_signup_form"):
            new_uid = st.text_input("Choose Unique Student User ID", placeholder="e.g., pramik_cst")
            new_pwd = st.text_input("Set Secure Account Password", type="password", placeholder="Minimum 6 characters recommended...")
            confirm_pwd = st.text_input("Confirm Account Password", type="password", placeholder="Retype your chosen password...")
            if st.form_submit_button("Register Account Infrastructure 💾", use_container_width=True):
                if not new_uid.strip() or not new_pwd.strip():
                    st.error("Fields cannot be blank.")
                elif new_pwd != confirm_pwd:
                    st.error("Password confirmation keys do not match.")
                else:
                    if register_user_in_db(new_uid.strip(), new_pwd.strip()):
                        st.success("🎉 Account committed successfully! Switch to the Student Login tab to access your workspace.")
                    else:
                        st.error("⚠️ Username token already exists in system records.")
                        
    with tab_admin:
        with st.form("admin_login_form"):
            a_name = st.text_input("Admin Master Key ID", placeholder="Enter admin user...")
            a_pass = st.text_input("Master Password Profile", type="password", placeholder="Enter verification pass...")
            if st.form_submit_button("Unlock Root Systems 🔓", use_container_width=True):
                if a_name == ADMIN_UID and a_pass == ADMIN_PWD:
                    st.session_state.login_role = "admin"
                    st.session_state.login_username = "SYSTEM_ADMIN"
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
#  3. WEB INTEGRATED RETRIEVAL EXTRACTOR TELEMETRIES (RAG)
# =====================================================================
def get_live_weather(location_query: str) -> str:
    try:
        clean_loc = location_query.strip() + ", India" if "india" not in location_query.lower() else location_query.strip()
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(clean_loc)}&count=1&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=5).json()
        if not geo_res.get("results"): return ""
        node = geo_res["results"][0]
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={node['latitude']}&longitude={node['longitude']}&current=temperature_2m,apparent_temperature,relative_humidity_2m&timezone=auto"
        curr = requests.get(weather_url, timeout=5).json()["current"]
        return f"\n[Live Meteorological Telemetry: {node['name']} -> Temperature: {curr['temperature_2m']}°C, RealFeel: {curr['apparent_temperature']}°C, Humidity: {curr['relative_humidity_2m']}%]"
    except Exception: return ""

def get_world_news(regional_query: str) -> str:
    try:
        topic = regional_query.strip() + " India" if "india" not in regional_query.lower() else regional_query.strip()
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={requests.utils.quote(topic)}&hl=en-IN&gl=IN&ceid=IN:en")
        return f"\n[Press Wire News: {' | '.join([e.title.split(' - ')[0] for e in feed.entries[:2]])}]"
    except Exception: return ""

def query_live_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            res = [r for r in ddgs.text(query, max_results=2)]
        return f"\n[Search Engine Context Index: {' '.join([r.get('body','') for r in res])}"
    except Exception: return ""

# =====================================================================
#  4. SIDEBAR CONFIGURATION & CONTROL GRIDS
# =====================================================================
with st.sidebar:
    st.image("https://img.icons8.com/nolan/128/artificial-intelligence.png", width=50)
    st.title("OmniCore Workspace")
    st.caption(f"Active User: `{st.session_state.login_username}`")
    st.caption("☁️ Cloud Server Offloaded Inference Engine Enabled")
    
    st.markdown("---")
    # REQUIREMENT 3: Persona Mapping Selectbox Component Router
    cfg_tone = st.selectbox("🎭 Engine Persona Matrix", ["Standard Agent", "Expert Professor", "Code Auditor", "Brief Summary Node"])
    
    # PRIVACY MASK: Admin panel only displays User IDs and handles access toggle states
    if st.session_state.login_role == "admin":
        st.markdown("---")
        st.subheader("👥 Registered User Status Node")
        st.caption("Review user indices or deactivate network privileges:")
        
        user_rows = fetch_all_users_raw()
        if user_rows:
            for uid_tag, active_flag in user_rows:
                col_name, col_action = st.columns([6.0, 4.0])
                with col_name:
                    status_emoji = "🟢" if int(active_flag) == 1 else "🔴"
                    st.markdown(f"{status_emoji} `{uid_tag}`")
                with col_action:
                    if int(active_flag) == 1:
                        if st.button("Deactivate", key=f"deact_{uid_tag}", use_container_width=True):
                            change_user_status_db(uid_tag, 0)
                            st.toast(f"Suspended workspace permissions for {uid_tag}!")
                            time.sleep(0.4)
                            st.rerun()
                    else:
                        if st.button("Activate", key=f"act_{uid_tag}", use_container_width=True):
                            change_user_status_db(uid_tag, 1)
                            st.toast(f"Re-activated workspace permissions for {uid_tag}!")
                            time.sleep(0.4)
                            st.rerun()
        else:
            st.caption("Zero student accounts registered in system records.")
            
    # REQUIREMENT 6: Side-mounted Historical Prompt Sync Menu
    if st.session_state.login_role == "user" or st.session_state.login_role == "admin":
        st.markdown("---")
        st.subheader("📋 Recent Sidebar Queries")
        sidebar_history_links = get_unique_sidebar_titles(st.session_state.login_username)
        if sidebar_history_links:
            for past_link_title in sidebar_history_links:
                if st.button(f"💬 {past_link_title}", key=f"side_{past_link_title}", use_container_width=True):
                    st.session_state.active_display = past_link_title
                    st.session_state.active_payload = past_link_title
                    st.rerun()
        else:
            st.caption("No session queries stored yet.")
            
    st.markdown("---")
    if st.button("Initialize Fresh Session Layout", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.active_payload = ""
        st.session_state.active_display = ""
        st.rerun()

    if st.button("Log Out and Exit System", use_container_width=True):
        st.session_state.login_role = None
        st.session_state.login_username = None
        st.session_state.chat_history = []
        st.rerun()

# =====================================================================
#  5. MAIN PAGE LAYOUT ENGINE (REQUIREMENT 1: LANDING WITH SEARCH FIRST)
# =====================================================================
# Hides conversation arrays completely if session history is blank, forcing search bar layout first
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

# REQUIREMENT 4: Hardware Camera Capture Framework & Multimodal Document Buffers
col_file, col_cam, col_mic = st.columns([4.5, 4.5, 3.0])
file_context, camera_context, mic_transcription = "", "", None

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

with col_cam:
    st.markdown("**📷 Trigger Live Hardware Camera Capturing Node**")
    cam_shot = st.camera_input("Hardware Matrix Capture Input", label_visibility="collapsed")
    if cam_shot is not None:
        camera_context = f"\n[SYSTEM CAMERA SNAPSHOT BUFFER EXTRACTION NODE: {len(cam_shot.getvalue())} bytes]"
        st.success("Hardware capture frame buffer locked into prompt matrix context!")

with col_mic:
    st.markdown("**🎙️ Record Audio Voice Prompts**")
    mic_transcription = speech_to_text(start_prompt="Record Voice 🎙️", stop_prompt="Halt 🟥", language="en", just_once=True)

# Central Search Container Form Interface (Primary Homepage Core Element Viewport)
with st.form("central_agent_search_boundary", clear_on_submit=True):
    col_field, col_btn = st.columns([10.0, 2.0])
    with col_field:
        ui_input = st.text_input("Core System Search", placeholder="Input analytical requirements, code parameters, or request live regional Indian telemetry updates...", label_visibility="collapsed")
    with col_btn:
        triggered = st.form_submit_button("Query Engine 🚀", use_container_width=True)

# Synchronization logic bounds
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
    if cam_shot: display_string += " 📷 (Attached Camera Screenshot Capture Context Frame)"
    
    payload_string = f"{final_query} {file_context} {camera_context}"
    
    st.session_state.chat_history.append({"role": "user", "content": display_string})
    save_message(st.session_state.login_username, "user", display_string)
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        # REQUIREMENT 10: High-Contrast Animated Thinking Loader Placeholder View (0% Clean Raw Text Markdown Output)
        placeholder.markdown("🧠 **Thinking... accessing serverless cloud layers... [0% local system load matching]**")
        
        # Execute Live Tools
        web_data = ""
        q_low = final_query.lower()
        if any(x in q_low for x in ["weather", "temperature", "temp", "climate"]):
            web_data = get_live_weather("Nalhati, West Bengal")
        elif any(x in q_low for x in ["news", "bulletin", "headlines", "affairs"]):
            web_data = get_world_news("Nalhati, West Bengal")
        else:
            web_data = query_live_search(final_query)
            
        rules = f"""You are the premium cloud-offloaded intelligence layer of 'Offline.Ai', built by Mrinal Gorain from Nalhati Government Polytechnic, CST department.
Project portfolio documentation was compiled by Prami Hazra and Sanchari Choudhury.
Persona Setting: {cfg_tone}

CRITICAL MATHEMATICAL LATEX FORMATTING RULES:
- Use $inline$ for running equations and $$display$$ notation blocks for standalone multi-line equations.

CRITICAL REGIONAL LANGUAGE SCRIPTS DIRECTIVE:
- If user uses Bengali, reply in BENGALI SCRIPT (বাংলা হরফ). If Hindi, reply in HINDI SCRIPT (देवनागरी).

CONTEXT REFERENCE PACK:
{web_data}
"""
        
        # High-Performance Remote Cloud Provider Routing Layer (Requirement 9 & 10 Combined)
        headers = {"Authorization": CLOUD_API_KEY, "Content-Type": "application/json"}
        prompt_payload = f"System Rules:\n{rules}\nUser Prompt:\n{payload_string}\nAssistant:"
        
        try:
            t_start = time.time()
            response = requests.post(CLOUD_INFERENCE_URL, headers=headers, json={"inputs": prompt_payload, "parameters": {"max_new_tokens": 600, "temperature": 0.15}}, timeout=15)
            t_delta = time.time() - t_start
            
            res_json = response.json()
            if isinstance(res_json, list) and len(res_json) > 0:
                raw_txt = res_json[0].get("generated_text", "Cloud parsing completed.")
                full_text = raw_txt.split("Assistant:")[-1].strip()
            else:
                full_text = "Cloud token pipeline returned an unparsed response array. Check authorization key codes."
                
            if t_delta > 0:
                st.session_state.speed_telemetry = f"{round(len(full_text.split()) / t_delta, 1)} words/sec (Serverless Compute)"
            
            # Displays response inside a static structural card container without outputting messy div tags
            placeholder.markdown(full_text)
            
            st.session_state.chat_history.append({"role": "assistant", "content": full_text})
            save_message(st.session_state.login_username, "assistant", full_text)
        except Exception as ex:
            placeholder.error(f"Cloud Inference Connection Exception: {str(ex)}")
                
    # REQUIREMENT 5: Smooth Automated Screen Viewport Scrolling Core Script Layer
    st.components.v1.html("""
        <script>
            var viewport = window.parent.document.querySelector('.main');
            if (viewport) { viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' }); }
        </script>
    """, height=0)
    st.rerun()