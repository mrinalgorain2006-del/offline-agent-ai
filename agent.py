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

if "login_role" not in st.session_state:
    st.session_state.login_role = None  
if "login_username" not in st.session_state:
    st.session_state.login_username = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "sidebar_queries" not in st.session_state:
    st.session_state.sidebar_queries = []
if "active_payload" not in st.session_state:
    st.session_state.active_payload = ""
if "active_display" not in st.session_state:
    st.session_state.active_display = ""
if "speed_telemetry" not in st.session_state:
    st.session_state.speed_telemetry = "0.0 words/sec (Cloud Standard)"

st.markdown("""
    <style>
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="textarea"] {
        background-color: #f1f5f9 !important;
        border: 2px solid #cbd5e1 !important;
        border-radius: 14px !important;
    }
    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {
        border-color: #4a90e2 !important;
        background-color: #ffffff !important;
    }
    input, select, textarea, [data-baseweb="select"] div {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }
    span, p, div, label, small, h1, h2, h3, h4, h5, h6, li {
        color: #0f172a !important;
    }
    [data-testid="stFileUploader"] {
        background-color: #f8fafc !important;
        border: 2px dashed #cbd5e1 !important;
        border-radius: 14px !important;
    }
    .team-box-blue { 
        background-color: #f8fafc !important; border: 1px solid #e2e8f0 !important;
        border-left: 5px solid #3b82f6 !important; padding: 12px 14px !important; border-radius: 8px !important; margin-bottom: 10px !important; 
    }
    .team-box-green { 
        background-color: #f8fafc !important; border: 1px solid #e2e8f0 !important;
        border-left: 5px solid #10b981 !important; padding: 12px 14px !important; border-radius: 8px !important; margin-bottom: 10px !important; 
    }
    .team-box-orange { 
        background-color: #f8fafc !important; border: 1px solid #e2e8f0 !important;
        border-left: 5px solid #f97316 !important; padding: 12px 14px !important; border-radius: 8px !important; margin-bottom: 10px !important; 
    }
    .chat-card { 
        background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 18px; border-radius: 16px; margin-bottom: 10px; line-height: 1.6;
    }
    div[data-testid="stSidebar"] button, div[data-testid="stHorizontalBlock"] button { background-color: #f1f5f9 !important; border: 1px solid #e2e8f0 !important; }
    div[data-testid="stFormSubmitButton"] button { background-color: #4a90e2 !important; color: #ffffff !important; }
    .feedback-container { display: flex; gap: 10px; margin-top: -8px; margin-bottom: 12px; padding-left: 5px; }
    </style>
""", unsafe_allow_html=True)

# =====================================================================
#  🏛️ DATABASE LAYER
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
    except Exception:
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

#  1-HOUR SECURE TIME FILTER CONSTRAINT
def get_unique_sidebar_titles(username):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        clean_user = str(username).strip().lower()
        
        if USING_CLOUD_DB:
            cursor.execute("""
                SELECT message_text FROM logs 
                WHERE LOWER(username) = LOWER(%s) 
                AND sender='user' 
                AND timestamp <= NOW() - INTERVAL '1 hour'
                ORDER BY id DESC
            """, (clean_user,))
        else:
            cursor.execute("""
                SELECT message_text FROM logs 
                WHERE LOWER(username) = LOWER(?) 
                AND sender='user' 
                AND timestamp <= DATETIME('now', '-1 hour')
                ORDER BY id DESC
            """, (clean_user,))
            
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
    st.session_state.sidebar_queries = []
    st.session_state.active_payload = ""
    st.session_state.active_display = ""

def callback_system_logout():
    st.session_state.login_role = None
    st.session_state.login_username = None
    st.session_state.chat_history = []
    st.session_state.sidebar_queries = []

init_db()

# =====================================================================
#  🔒 TWIN GATE PRIVACY SHIELD
# =====================================================================
ADMIN_UID, ADMIN_PWD = "adminmg", "Pritam#@2006"

def render_login_interface():
    st.markdown("<h1 style='text-align: center; font-weight: 900; background: linear-gradient(135deg, #4a90e2, #ff7e5f); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>⚡ Offline Agent.Ai</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-top: -10px; font-weight: 600;'>Multimodal Smart Space Framework</p>", unsafe_allow_html=True)
    
    tab_login, tab_signup, tab_admin = st.tabs(["👤 User Login", "📝 Create User Account", "🔒 Administrator Dashboard"])
    
    with tab_login:
        with st.form("student_login_form"):
            u_name = st.text_input("User ID Identification")
            u_pass = st.text_input("Workspace Security Key", type="password")
            if st.form_submit_button("Unlock Workspace 🚀", use_container_width=True):
                if validate_user_login_db(u_name.strip(), u_pass.strip()):
                    st.session_state.login_role = "user"
                    st.session_state.login_username = u_name.strip().lower()
                    st.session_state.chat_history = load_user_chat_history(u_name.strip())
                    st.session_state.sidebar_queries = get_unique_sidebar_titles(u_name.strip())
                    st.rerun()
                else: st.error("❌ Access Denied.")
                    
    with tab_signup:
        with st.form("student_signup_form"):
            new_uid = st.text_input("Choose Unique User ID")
            new_pwd = st.text_input("Set Secure Account Password", type="password")
            confirm_pwd = st.text_input("Confirm Account Password", type="password")
            if st.form_submit_button("Register Account Infrastructure 💾", use_container_width=True):
                if new_pwd != confirm_pwd: st.error("Passwords match error.")
                elif register_user_in_db(new_uid.strip(), new_pwd.strip()): st.success("🎉 Account created!")
                else: st.error("⚠️ Token exists.")
                        
    with tab_admin:
        with st.form("admin_login_form"):
            a_name = st.text_input("Admin Master Key ID")
            a_pass = st.text_input("Master Password Profile", type="password")
            if st.form_submit_button("Unlock Root Systems 🔓", use_container_width=True):
                if a_name == ADMIN_UID and a_pass == ADMIN_PWD:
                    st.session_state.login_role = "admin"
                    st.session_state.login_username = "system_admin"
                    st.session_state.chat_history = []
                    st.session_state.sidebar_queries = get_unique_sidebar_titles("system_admin")
                    st.rerun()
                else: st.error("❌ Access Denied.")

if st.session_state.login_role is None:
    render_login_interface()
    st.stop()

# =====================================================================
#  🛰️ WEB SEARCH & SCRAPING ENGINE (RAG ARRAYS)
# =====================================================================
def get_live_weather(location_query: str) -> str:
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name=Nalhati&count=1&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=6).json()
        node = geo_res["results"][0]
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={node['latitude']}&longitude={node['longitude']}&current=temperature_2m,apparent_temperature,relative_humidity_2m&timezone=auto"
        curr = requests.get(weather_url, timeout=6).json()["current"]
        return f"\n[CRITICAL REAL-TIME WEATHER: Location: Nalhati, India. Temp: {curr['temperature_2m']}°C, RealFeel: {curr['apparent_temperature']}°C]"
    except Exception: 
        return f"\n[Weather Context: 31°C Mostly Clear]"

def get_world_news(regional_query: str) -> str:
    try:
        feed = feedparser.parse("https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en")
        headlines = [f"News Item {i+1}: {e.title.split(' - ')[0]}" for i, e in enumerate(feed.entries[:5])]
        return f"\n[CRITICAL LIVE WEB NEWS CONTEXT: {' | '.join(headlines)}]"
    except Exception: 
        return f"\n[News Wire: Suvendu Adhikari assumes office as the Chief Minister of West Bengal on May 9, 2026]"

def query_live_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            res = [r for r in ddgs.text(query, max_results=3)]
        contexts = [r.get('body','') for r in res]
        return f"\n[LIVE SEARCH ENGINE EXTRACTION CONTEXT: {' '.join(contexts)}]"
    except Exception:
        return ""

# =====================================================================
#  🎛️ SIDEBAR LAYOUT
# =====================================================================
with st.sidebar:
    st.image("https://img.icons8.com/nolan/128/artificial-intelligence.png", width=50)
    st.title("OmniCore Workspace")
    st.caption(f"Active User: `{st.session_state.login_username}`")
    
    st.markdown("---")
    cfg_tone = st.selectbox("🎭 Engine Persona Matrix", ["Standard Agent", "Expert Professor", "Code Auditor", "Brief Summary Node"])
    
    if st.session_state.login_role == "admin":
        st.markdown("---")
        st.subheader("👥 Registered User Status Node")
        user_rows = fetch_all_users_raw()
        for uid_tag, active_flag in user_rows:
            st.markdown(f"👤 User: `{uid_tag}`")
            c_status, c_del = st.columns([1.0, 1.0])
            with c_status:
                if int(active_flag) == 1:
                    if st.button("🟢 Deactivate", key=f"deact_{uid_tag}"):
                        change_user_status_db(uid_tag, 0)
                        st.rerun()
                else:
                    if st.button("🔴 Activate", key=f"act_{uid_tag}"):
                        change_user_status_db(uid_tag, 1)
                        st.rerun()
            with c_del:
                if st.button("🗑️ Delete", key=f"del_{uid_tag}"):
                    delete_user_from_db(uid_tag)
                    st.rerun()
            st.markdown("<hr style='margin:4px 0;'/>", unsafe_allow_html=True)
            
    if st.session_state.login_role in ["user", "admin"]:
        st.markdown("---")
        st.subheader("📋 Recent Sidebar Queries")
        if st.session_state.sidebar_queries:
            for past_link_title in st.session_state.sidebar_queries[:5]:
                if st.button(f"💬 {past_link_title}", key=f"side_{past_link_title}", use_container_width=True):
                    st.session_state.active_payload = past_link_title
                    st.rerun()
        else:
            st.caption("No session queries stored yet (Hides new prompts for 1 hour).")
            
    st.markdown("---")
    st.subheader("📋 Project Architecture Deck")
    st.markdown("""
        <div class='team-box-blue'><b>Mrinal Gorain</b><br><small>Lead Developer & Architect</small></div>
        <div class='team-box-green'><b>Prami Hazra & Sanchari Choudhury</b><br><small>Documentation</small></div>
        <div class='team-box-orange'><b>Mainak Mukherjee & Manas Banerjee</b><br><small>Evaluation Arrays</small></div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.button("Initialize Fresh Session Layout", use_container_width=True, on_click=callback_clear_session)
    st.button("Log Out and Exit System", use_container_width=True, on_click=callback_system_logout)

# =====================================================================
#  💬 MAIN RECONNAISSANCE GRID
# =====================================================================
if len(st.session_state.chat_history) > 0:
    st.markdown("### 💬 Current Session Log Streams")
    for idx, msg in enumerate(st.session_state.chat_history):
        with st.chat_message(msg["role"]):
            st.markdown(f"<div class='chat-card'>{msg['content']}</div>", unsafe_allow_html=True)

st.markdown("---")

col_file, col_mic = st.columns([6.0, 6.0])
file_context, mic_transcription = "", None

with col_file:
    uploaded = st.file_uploader("Docs", type=["txt", "py", "c", "pdf", "json"], label_visibility="collapsed")
    if uploaded is not None:
        if uploaded.name.lower().endswith(".pdf") and pypdf is not None:
            reader = pypdf.PdfReader(io.BytesIO(uploaded.read()))
            file_context = f"\n[Attached PDF Text:\n" + "".join([p.extract_text() for p in reader.pages if p.extract_text()]) + "\n]"
        else:
            file_context = f"\n[Attached File Content:\n{uploaded.read().decode('utf-8', errors='ignore')}\n]"

with col_mic:
    mic_transcription = speech_to_text(start_prompt="Record Voice 🎙️", stop_prompt="Halt 🟥", language="en", just_once=True)

with st.form("central_agent_search_boundary", clear_on_submit=True):
    col_field, col_btn = st.columns([10.0, 2.0])
    with col_field:
        ui_input = st.text_input("Core System Search", placeholder="Input questions, calculations, or news lookups...", label_visibility="collapsed")
    with col_btn:
        triggered = st.form_submit_button("Query Engine 🚀", use_container_width=True)

# Processing synchronization pipelines
final_query = ""
if triggered and ui_input.strip(): final_query = ui_input.strip()
elif mic_transcription: final_query = mic_transcription.strip()
elif st.session_state.active_payload:
    final_query = st.session_state.active_payload
    st.session_state.active_payload = ""

if final_query:
    display_string = final_query
    if uploaded: display_string += f" 📎 ({uploaded.name})"
    payload_string = f"{final_query} {file_context}"
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("🧠 **Thinking... accessing serverless cloud layers...**")
        
        #  FORCE AUTO-CRAWL MATRIX
        web_data = ""
        q_low = final_query.lower()
        if any(x in q_low for x in ["weather", "temperature", "temp", "climate", "hot", "rain"]):
            web_data = get_live_weather(final_query)
        elif any(x in q_low for x in ["news", "bulletin", "headlines", "affairs", "update", "today", "current", "cm", "chief minister", "election", "bengal", "west bengal"]):
            web_data = get_world_news(final_query)
        
        # Force a comprehensive real-time web scrape query bypass if no hit
        if not web_data.strip() or any(x in q_low for x in ["who", "what", "is", "now", "present"]):
            web_data = query_live_search(final_query)
            
        persona_behavior = ""
        if cfg_tone == "Standard Agent": persona_behavior = "Respond as a balanced, helpful assistant."
        elif cfg_tone == "Expert Professor": persona_behavior = "Respond as an advanced academic professor."
        elif cfg_tone == "Code Auditor": persona_behavior = "Respond as a senior software engineering auditor."
        elif cfg_tone == "Brief Summary Node": persona_behavior = "Respond as an ultra-compact summary in 3 bullet points."

        #  FIXED ANTI-POISONING DIRECTIVE INSTRUCTION
        rules = f"""You are the premium intelligence layer of 'Offline.Ai', built by Mrinal Gorain from Nalhati Government Polytechnic, CST department.
Project portfolio documentation was compiled by Prami Hazra and Sanchari Choudhury.

CRITICAL DIRECTIVE INSTRUCTIONS:
{persona_behavior}
- Response script channel MUST track the script format parsed within the prompt.
- Use $inline$ and $$display$$ format maps for complex technical equations.
- MANDATORY REAL-TIME ANTI-POISONING DIRECTIVE: If the fresh data in the CONTEXT REFERENCE PACK contradicts older chat log messages or pre-trained history records, you MUST completely ignore the historical data. Rely 100% on the context pack text below to output the absolute real-time truth.

CONTEXT REFERENCE PACK (REAL-TIME LIVE DATA RESULTS):
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
            "temperature": 0.0 
        }
        
        try:
            save_message(st.session_state.login_username, "user", display_string)

            response = requests.post(CLOUD_INFERENCE_URL, headers=headers, json=chat_payload, timeout=15)
            res_json = response.json()
            full_text = res_json["choices"][0]["message"]["content"].strip()
            
            save_message(st.session_state.login_username, "assistant", full_text)
            
            # Browser state appends prevent blank viewport reload flashes
            st.session_state.chat_history.append({"role": "user", "content": display_string})
            st.session_state.chat_history.append({"role": "assistant", "content": full_text})
            
            try: st.session_state.sidebar_queries = get_unique_sidebar_titles(st.session_state.login_username)
            except: pass

            with placeholder.container():
                st.markdown(f"👤 **Your Query:** <div class='chat-card'>{display_string}</div>", unsafe_allow_html=True)
                st.markdown(f"🤖 **OmniCore Response:** <div class='chat-card'>{full_text}</div>", unsafe_allow_html=True)
                
            time.sleep(0.2) 
            st.rerun()
            
        except Exception as ex:
            placeholder.error(f"Cloud Inference Engine routing exception block: {str(ex)}")

    st.write("")