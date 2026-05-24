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
import uuid
import wikipedia  # Safe, open-source Wikipedia engine completely compatible with your environments

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
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = str(uuid.uuid4())

# Professional Premium Styling Customization (Light-Themed Modern Look)
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
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    div[data-testid="stSidebar"] button, div[data-testid="stHorizontalBlock"] button { background-color: #f1f5f9 !important; border: 1px solid #e2e8f0 !important; }
    div[data-testid="stFormSubmitButton"] button { background-color: #4a90e2 !important; color: #ffffff !important; }
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
    
    cursor.execute(f"CREATE TABLE IF NOT EXISTS logs (id {auto_inc}, username TEXT, session_id TEXT, sender TEXT, message_text TEXT, timestamp {ts_type})")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS reinforcement_feedback (id {auto_inc}, prompt TEXT, response TEXT, reward_score INTEGER, timestamp {ts_type})")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS student_profiles (id {auto_inc}, student_uid TEXT UNIQUE, student_pwd TEXT, is_active INTEGER DEFAULT 1, timestamp {ts_type})")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS chat_sessions (id {auto_inc}, username TEXT, session_id TEXT UNIQUE, folder_title TEXT, timestamp {ts_type})")
    conn.commit()
    cursor.close()
    conn.close()

def save_message(username, session_id, sender, text):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        
        target_user = str(username).strip().lower() if username else "anonymous_node"
        
        if target_user != "":
            cursor.execute(f"SELECT session_id FROM chat_sessions WHERE session_id={param}", (session_id,))
            if not cursor.fetchone() and sender == "user":
                clean_title = text.replace("📎", "").split('\n')[0].strip()
                folder_name = clean_title[:28] + "..." if len(clean_title) > 28 else clean_title
                if not folder_name:
                    folder_name = "New Agent Conversation Thread..."
                    
                cursor.execute(f"INSERT INTO chat_sessions (username, session_id, folder_title) VALUES ({param}, {param}, {param})", (target_user, session_id, folder_name))
            
            cursor.execute(f"INSERT INTO logs (username, session_id, sender, message_text) VALUES ({param}, {param}, {param}, {param})", (target_user, session_id, sender, text))
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
        if not clean_uid:
            cursor.close()
            conn.close()
            return False
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
        if not clean_uid or not str(pwd).strip():
            cursor.close()
            conn.close()
            return False
        cursor.execute(f"SELECT student_pwd, is_active FROM student_profiles WHERE LOWER(student_uid) = LOWER({param})", (clean_uid,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row and row[0] == pwd and int(row[1]) == 1:
            return True
        return False
    except Exception:
        return False

def recover_user_password_db(uid):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        clean_uid = str(uid).strip().lower()
        cursor.execute(f"SELECT student_pwd, is_active FROM student_profiles WHERE LOWER(student_uid) = LOWER({param})", (clean_uid,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            if int(row[1]) == 1:
                return {"status": "success", "password": row[0]}
            else:
                return {"status": "deactivated"}
        return {"status": "not_found"}
    except Exception:
        return {"status": "error"}

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
        return True
    except Exception:
        return False

def delete_entire_session_db(session_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"DELETE FROM logs WHERE session_id = {param}", (session_id,))
        cursor.execute(f"DELETE FROM chat_sessions WHERE session_id = {param}", (session_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass

def load_session_chat_history(session_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        cursor.execute(f"SELECT sender, message_text FROM logs WHERE session_id = {param} ORDER BY id ASC", (session_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [{"role": row[0], "content": row[1]} for row in rows]
    except Exception:
        return []

def get_session_folders_structure(username):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "%s" if USING_CLOUD_DB else "?"
        target_user = str(username).strip().lower() if username else "anonymous_node"
        
        cursor.execute(f"SELECT session_id, folder_title FROM chat_sessions WHERE LOWER(username) = LOWER({param}) ORDER BY id DESC", (target_user,))
        folders = cursor.fetchall()
        
        structure = []
        for sess_id, title in folders:
            cursor.execute(f"SELECT message_text FROM logs WHERE session_id={param} AND sender='user' ORDER BY id ASC", (sess_id,))
            prompts = [r[0] for r in cursor.fetchall()]
            structure.append({"session_id": sess_id, "folder_title": title, "sub_prompts": prompts})
            
        cursor.close()
        conn.close()
        return structure
    except Exception:
        return []

def callback_clear_session():
    st.session_state.chat_history = []
    st.session_state.active_payload = ""
    st.session_state.current_session_id = str(uuid.uuid4())

def callback_system_logout():
    st.session_state.login_role = None
    st.session_state.login_username = None
    st.session_state.chat_history = []
    st.session_state.current_session_id = str(uuid.uuid4())

init_db()

# =====================================================================
#  🔒 SECURITY ACCESS PATTERNS WITH RECOVERY SYSTEM
# =====================================================================
ADMIN_UID, ADMIN_PWD = "adminmg", "Pritam#@2006"

def render_login_interface():
    st.markdown("<h1 style='text-align: center; font-weight: 900; background: linear-gradient(135deg, #4a90e2, #ff7e5f); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>⚡ Offline Agent.Ai</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-top: -10px; font-weight: 600;'>Advanced Multimodal Automation Hub</p>", unsafe_allow_html=True)
    
    tab_login, tab_signup, tab_forgot, tab_admin = st.tabs(["👤 User Access Login", "📝 Create Secure Account", "🔑 Forgot Key Recovery", "🔒 Administrator Hub Portal"])
    
    with tab_login:
        with st.form("student_login_form"):
            u_name = st.text_input("User Token Identification", placeholder="Enter username...")
            u_pass = st.text_input("Workspace Privacy Key", type="password", placeholder="Enter account security code...")
            if st.form_submit_button("Unlock Interactive Workspace 🚀", use_container_width=True):
                if not u_name.strip() or not u_pass.strip():
                    st.error("❌ Inputs cannot be left empty.")
                elif validate_user_login_db(u_name.strip(), u_pass.strip()):
                    st.session_state.login_role = "user"
                    st.session_state.login_username = u_name.strip().lower()
                    st.session_state.chat_history = []
                    st.session_state.current_session_id = str(uuid.uuid4())
                    st.rerun()
                else: 
                    st.error("❌ Invalid authorization parameters.")
                    
    with tab_signup:
        with st.form("student_signup_form"):
            new_uid = st.text_input("Claim Unique ID Node", placeholder="e.g., student_workspace_01")
            new_pwd = st.text_input("Set Access Protection Password", type="password")
            confirm_pwd = st.text_input("Verify Access Protection Password", type="password")
            if st.form_submit_button("Register Core Architecture Node 💾", use_container_width=True):
                if not new_uid.strip() or not new_pwd.strip():
                    st.error("❌ Registration Blocked: Input sequences cannot be blank.")
                elif len(new_pwd.strip()) < 4:
                    st.error("❌ Password sequence requirement: Minimum 4 units.")
                elif new_pwd.strip() != confirm_pwd.strip(): 
                    st.error("❌ Password alignment validation failed.")
                else:
                    if register_user_in_db(new_uid.strip(), new_pwd.strip()): 
                        st.success("🎉 Node registered! Proceed to login panel.")
                    else: 
                        st.error("⚠️ Username token conflict across registry arrays.")

    with tab_forgot:
        st.markdown("### 🔑 Account Password Retrieval Protocol")
        with st.form("password_recovery_form"):
            recovery_uid = st.text_input("Registered User ID Token", placeholder="Type your User ID here...")
            if st.form_submit_button("Retrieve Password Key 🔓", use_container_width=True):
                if not recovery_uid.strip():
                    st.error("❌ Please provide a valid User ID token to run lookups.")
                else:
                    result = recover_user_password_db(recovery_uid.strip())
                    if result["status"] == "success":
                        st.success(f"🔑 Core Match Found! Your registered Workspace Privacy Key is: **{result['password']}**")
                    elif result["status"] == "deactivated":
                        st.warning("⚠️ Access Registry Alert: That account node is currently deactivated by the admin.")
                    elif result["status"] == "not_found":
                        st.error("❌ No profile record matches that User ID token within the database ledger.")
                    else:
                        st.error("❌ Processing fault along backend database connections.")
                        
    with tab_admin:
        with st.form("admin_login_form"):
            a_name = st.text_input("Admin Matrix ID")
            a_pass = st.text_input("Master Secure Authorization Pass", type="password")
            if st.form_submit_button("Authenticate Administrative Shell 🔓", use_container_width=True):
                if a_name == ADMIN_UID and a_pass == ADMIN_PWD:
                    st.session_state.login_role = "admin"
                    st.session_state.login_username = "system_admin"
                    st.session_state.chat_history = []
                    st.session_state.current_session_id = str(uuid.uuid4())
                    st.rerun()
                else: 
                    st.error("❌ Administrative validation failed.")

if st.session_state.login_role is None:
    render_login_interface()
    st.stop()

# =====================================================================
#  🛰️ MULTI-STAGE RETRIEVAL ENGINE (WIKIPEDIA + GOOGLE FALLBACK)
# =====================================================================
def query_wikipedia_layer(query: str) -> str:
    """Integrated lookup module pulling clean data from Wikipedia natively."""
    try:
        wikipedia.set_user_agent("OfflineAgentAI/1.0 (cst_dept@polytechnic.edu)")
        summary_text = wikipedia.summary(query, sentences=3)
        if summary_text:
            return f"\n[OFFICIAL WIKIPEDIA FACTUAL DATABASE MATRIX:\nTopic context: {query}\nVerified Data: {summary_text}\n---]"
    except wikipedia.exceptions.DisambiguationError as e:
        try:
            alt_summary = wikipedia.summary(e.options[0], sentences=2)
            return f"\n[OFFICIAL WIKIPEDIA FACTUAL MATRIX (Resolved alternative): {alt_summary}]"
        except: pass
    except Exception:
        pass
    return ""

def query_live_search(query: str) -> str:
    """Dynamic multi-tier fallback searching mechanism mimicking enterprise agents."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            res = [r for r in ddgs.text(query, max_results=4)]
        contexts = [f"Source URL: {r.get('href','')}\nSnippet Data: {r.get('body','')}\n---" for r in res]
        return f"\n[LIVE SEARCH ENGINE REFERENCE HARVESTPACK:\n{' '.join(contexts)}\n]"
    except Exception:
        try:
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en")
            headlines = [f"Scraped Insight: {e.title}" for e in feed.entries[:4]]
            return f"\n[REAL-TIME SEARCH RECOVERY MATRICES: {' | '.join(headlines)}]"
        except Exception:
            return "\n[Notice: Web harvesting layers are clear, running on foundational logic arrays.]"

# =====================================================================
#  🖥️ SAFE MARKDOWN VISUAL FORMATTER FUNCTION (PREVENTS HTML ACCIDENTALS)
# =====================================================================
def safe_render_chat_card(role_label, text_content):
    """Detects raw code markers to dynamically route rendering formats cleanly."""
    if "```" in text_content:
        st.markdown(f"⚡ **Offline Agent.Ai ({role_label} Mode) View:**")
        st.markdown(text_content)
    else:
        st.markdown(f"<div class='chat-card'><b>{role_label}:</b><br>{text_content}</div>", unsafe_allow_html=True)

# =====================================================================
#  🎛️ SIDEBAR INTERACTIVE CONSOLE CONTROL PANEL
# =====================================================================
with st.sidebar:
    st.markdown("<h2 style='margin:0; padding-bottom:10px;'>🤖 Offline Agent.Ai</h2>", unsafe_allow_html=True)
    st.caption(f"Secure Node ID: `{st.session_state.login_username}` | Layer: `{st.session_state.login_role.upper()}`")
    
    st.markdown("---")
    cfg_tone = st.selectbox("🎭 Active Agent Persona Matrix", ["Standard Agent", "Expert Professor", "Code Auditor", "Brief Summary Node"])
    
    if st.session_state.login_role == "user":
        st.markdown("<div style='background: #f1f5f9; padding: 12px; border-radius: 10px; margin-bottom: 10px;'>🌟 <b>User Workspace Active</b><br><small>Fully functional, autonomous pipeline ready.</small></div>", unsafe_allow_html=True)

    if st.session_state.login_role == "admin":
        st.markdown("---")
        st.subheader("🛠️ Core Administration Node")
        with st.expander("👤 Managed Accounts Ledger", expanded=True):
            user_rows = fetch_all_users_raw()
            for uid_tag, active_flag in user_rows:
                if uid_tag.strip() != "":
                    st.markdown(f"**Node UID:** `{uid_tag}`")
                    c_status, c_del = st.columns([1.0, 1.0])
                    with c_status:
                        if int(active_flag) == 1:
                            if st.button("🟢 Active", key=f"deact_{uid_tag}", use_container_width=True):
                                change_user_status_db(uid_tag, 0)
                                st.rerun()
                        else:
                            if st.button("🔴 Inactive", key=f"act_{uid_tag}", use_container_width=True):
                                change_user_status_db(uid_tag, 1)
                                st.rerun()
                    with c_del:
                        if st.button("🗑️ Wipe", key=f"del_{uid_tag}", use_container_width=True):
                            delete_user_from_db(uid_tag)
                            st.rerun()
                    st.markdown("<hr style='margin:6px 0; border: 0.5px solid #cbd5e1;'/>", unsafe_allow_html=True)
            
    # =====================================================================
    #  📂 NESTED SESSION HISTORY RECONSTRUCTION (CHATGPT STYLE FOLDERS)
    # =====================================================================
    st.markdown("---")
    st.subheader("📁 Session Prompt History Registry")
    
    session_folders = get_session_folders_structure(st.session_state.login_username)
    
    if session_folders:
        for folder in session_folders:
            with st.expander(f"📁 {folder['folder_title']}", expanded=(st.session_state.current_session_id == folder['session_id'])):
                col_load, col_wipe = st.columns([4.0, 1.0])
                with col_load:
                    if st.button("📂 Open Session", key=f"open_{folder['session_id']}", use_container_width=True):
                        st.session_state.current_session_id = folder['session_id']
                        st.session_state.chat_history = load_session_chat_history(folder['session_id'])
                        st.rerun()
                with col_wipe:
                    if st.button("🗑️", key=f"wipe_{folder['session_id']}", use_container_width=True):
                        delete_entire_session_db(folder['session_id'])
                        if st.session_state.current_session_id == folder['session_id']:
                            callback_clear_session()
                        st.rerun()
                
                st.markdown("<div style='padding-left:10px; border-left:2px solid #cbd5e1; margin-top:5px;'>", unsafe_allow_html=True)
                for q_idx, sub_prompt in enumerate(folder['sub_prompts'][:5]):
                    short_q = sub_prompt[:28] + "..." if len(sub_prompt) > 28 else sub_prompt
                    if st.button(f"📄 Q{q_idx+1}: {short_q}", key=f"sub_{folder['session_id']}_{q_idx}", use_container_width=True):
                        st.session_state.active_payload = sub_prompt
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.caption("No conversational history structures recorded.")
            
    st.markdown("---")
    st.subheader("📋 Academic Project Registry")
    st.markdown("""
        <div class='team-box-blue'><b>Mrinal Gorain</b><br><small>Lead Systems Developer</small></div>
        <div class='team-box-green'><b>Prami Hazra & Sanchari Choudhury</b><br><small>Technical Documentation Arrays</small></div>
        <div class='team-box-orange'><b>Mainak Mukherjee & Manas Banerjee</b><br><small>Strategic Evaluation Architecture</small></div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.button("Reset Shell View Canvas", use_container_width=True, on_click=callback_clear_session)
    st.button("Terminate Session Connection", use_container_width=True, on_click=callback_system_logout)

# =====================================================================
#  💬 INTERACTIVE DISPLAY STREAM 
# =====================================================================
st.markdown("<h2 style='margin-bottom:0;'>⚡ Offline Agent.Ai Dashboard</h2>", unsafe_allow_html=True)
st.caption(f"Session Token Array ID: `{st.session_state.current_session_id}`")

if not st.session_state.chat_history and st.session_state.current_session_id:
    st.session_state.chat_history = load_session_chat_history(st.session_state.current_session_id)

if len(st.session_state.chat_history) > 0:
    for idx, msg in enumerate(st.session_state.chat_history):
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                safe_render_chat_card(cfg_tone, msg['content'])
            else:
                st.markdown(f"<div class='chat-card'>{msg['content']}</div>", unsafe_allow_html=True)

st.markdown("---")

col_file, col_mic = st.columns([6.0, 6.0])
file_context, mic_transcription = "", None

with col_file:
    uploaded = st.file_uploader("Upload External Multi-Format Documents for RAG Embedding", type=["txt", "py", "c", "pdf", "json"], label_visibility="collapsed")
    if uploaded is not None:
        if uploaded.name.lower().endswith(".pdf") and pypdf is not None:
            reader = pypdf.PdfReader(io.BytesIO(uploaded.read()))
            file_context = f"\n[RAG ATTACHED PDF DATA INJECTION STREAM:\n" + "".join([p.extract_text() for p in reader.pages if p.extract_text()]) + "\n]"
        else:
            file_context = f"\n[RAG ATTACHED ENCODED FILE OBJECT INJECTION:\n{uploaded.read().decode('utf-8', errors='ignore')}\n]"

with col_mic:
    st.markdown("<div style='margin-bottom: 5px; font-weight: 500;'>🎙️ High-Fidelity Speech Processing (Whisper Alignment)</div>", unsafe_allow_html=True)
    mic_transcription = speech_to_text(start_prompt="Initialize Audio Recording System", stop_prompt="Halt Stream & Extract Matrix", language="en", just_once=True)

with st.form("central_agent_search_boundary", clear_on_submit=True):
    col_field, col_btn = st.columns([10.0, 2.0])
    with col_field:
        ui_input = st.text_input("Global Multi-Agent Entry Array", placeholder="Query anything... Fallback search protocols are actively monitoring input sequences.", label_visibility="collapsed")
    with col_btn:
        triggered = st.form_submit_button("Execute Run 🚀", use_container_width=True)

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
    
    # 🧠 =====================================================================
    #  ⚡ GEMINI-TYPE REAL-TIME INTENT ROUTER GATING SYSTEM
    # =====================================================================
    is_casual_greeting = final_query.strip().lower() in [
        "hi", "hello", "hey", "greetings", "good morning", "good afternoon", "yo", "sup"
    ]
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("🧠 **Offline Agent.Ai evaluating query routing intent...**")
        
        # Multi-stage fact retrieval execution (Bypassed if query is a simple greeting)
        if is_casual_greeting:
            fact_context = "[Notice: User has initialized a casual chat greeting. Reference pack generation unnecessary.]"
        else:
            fact_context = query_wikipedia_layer(final_query)
            if not fact_context.strip():
                fact_context = query_live_search(final_query)
            
        # =====================================================================
        #  🎯 ADAPTIVE PERSONA CONFIGURATION PATTERNS
        # =====================================================================
        active_temperature = 0.1
        if cfg_tone == "Standard Agent":
            active_temperature = 0.7  # Creative allowance for dynamic dialogue flow
            persona_behavior = """ROLE: You are an elite, natural general-purpose assistant.
            STYLE: Maintain a balanced, helpful, friendly, and highly clear conversational tone.
            OUTPUT RULES: If the user says 'Hi' or greets you, reply naturally with a warm welcome message (e.g., 'Hello! How can I assist you today?'). Do not analyze character definitions or alphabet positions."""
            
        elif cfg_tone == "Expert Professor":
            active_temperature = 0.6  # High explanatory flow parameters
            persona_behavior = """ROLE: You are an advanced university Academic Professor holding dual PhD credentials.
            STYLE: Deeply technical, pedagogical, exhaustive, and verbose. Use complex educational terminology.
            OUTPUT RULES: Break down theories, historical backgrounds, and cite fundamental theorems. If the user greets you with 'Hi', greet them back warmly as a mentor before initiating standard operational loops."""
            
        elif cfg_tone == "Code Auditor":
            active_temperature = 0.1  # Strict deterministic code checking layout
            persona_behavior = """ROLE: You are a ruthless Senior Software Security Auditor and System Architect.
            STYLE: Direct, highly analytical, objective, and entirely formal. No friendly chat or generic introductions. Output clean markdown code elements where code blocks are produced.
            OUTPUT RULES: Analyze data or problems purely through code fragments, execution tracking limits, syntax edge-cases, algorithms, big-O efficiency matrix scales, or robust infrastructure vulnerability models."""
            
        elif cfg_tone == "Brief Summary Node":
            active_temperature = 0.1  # Strict deterministic data compression
            persona_behavior = """ROLE: You are a high-speed data compression pipeline.
            STYLE: Ultra-compact, dense, and minimalist. 
            OUTPUT RULES: Compress your entire final answer into exactly three high-impact, short bullet points. Do not include introductory text, explanations, or sign-offs under any condition."""

        # =====================================================================
        #  📜 COMPREHENSIVE RULES SYSTEM (CLEANED OF RAW TAG BLEEDS)
        # =====================================================================
        rules = f"""System Context Configuration: You are the multi-agent system layer of 'Offline Agent.Ai', custom-engineered by Mrinal Gorain from Nalhati Government Polytechnic, Computer Science & Technology department.
Project portfolio records were compiled by Prami Hazra and Sanchari Choudhury.

MANDATORY STYLE AND REASONING LAWS:
{persona_behavior}

1. ABSOLUTE LIVE TRUTH ENFORCEMENT: Focus on the user input query vector. Answer directly, confidently, and naturally. If it is a greeting ("Hi", "Hello"), ignore historical definitions and greet them back dynamically.
2. ZERO META-TALK POLICY: You are completely banned from mentioning your training cutoff limits, dataset parameters, or saying phrases like "as of my knowledge cutoff" or "the data provided states". Never tell the user to verify information elsewhere—you are the final authority.
3. OUTPUT RESTRICTIONS: Do not add trailing math markup boxes ($ symbols), HTML div fragments, system prompt logs, code indexes, or formatting descriptions at the absolute end of your output screen box. Keep responses tightly contained inside your role style. Give only the clean answer text.

REAL-TIME CONTEXT REFERENCE OBJECT:
{fact_context}
"""
        headers = {"Authorization": CLOUD_API_KEY, "Content-Type": "application/json"}
        chat_payload = {
            "model": "meta-llama/Meta-Llama-3-8B-Instruct",
            "messages": [
                {"role": "system", "content": rules},
                {"role": "user", "content": payload_string}
            ],
            "max_tokens": 1200,
            "temperature": active_temperature  # Injects fluid creativity where required
        }
        
        try:
            save_message(st.session_state.login_username, st.session_state.current_session_id, "user", display_string)

            response = requests.post(CLOUD_INFERENCE_URL, headers=headers, json=chat_payload, timeout=18)
            res_json = response.json()
            
            if "choices" in res_json:
                full_text = res_json["choices"][0]["message"]["content"].strip()
                
                save_message(st.session_state.login_username, st.session_state.current_session_id, "assistant", full_text)
                st.session_state.chat_history.append({"role": "user", "content": display_string})
                st.session_state.chat_history.append({"role": "assistant", "content": full_text})
                
                with placeholder.container():
                    st.markdown(f"👤 **Your Input Query Vector:** <div class='chat-card'>{display_string}</div>", unsafe_allow_html=True)
                    safe_render_chat_card(cfg_tone, full_text)
                    
                time.sleep(0.1)
                st.rerun()
            else:
                error_msg = res_json.get("error", "Unknown cloud routing response mismatch.")
                placeholder.error(f"⚠️ Hugging Face Engine Exception: {error_msg}")
            
        except Exception as ex:
            placeholder.error(f"Cloud Inference Engine routing exception block: {str(ex)}")