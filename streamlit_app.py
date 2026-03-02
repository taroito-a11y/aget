import os
import time
from datetime import datetime
from html import escape
from typing import Dict, Optional

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_ASSISTANT_ID = "asst_CJffYUKAcUgyYHaDbroFkLEE"


def get_secret(key: str, default: str = "") -> str:
    value = st.secrets.get(key, os.getenv(key, default))
    return str(value).strip() if value is not None else ""


def get_client() -> OpenAI:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY が未設定です。Streamlit Cloud の Secrets か環境変数に設定してください。"
        )
    return OpenAI(api_key=api_key)


def get_assistant_id() -> str:
    return get_secret("OPENAI_ASSISTANT_ID", DEFAULT_ASSISTANT_ID)


def extract_text_from_message(message) -> str:
    chunks = []
    for item in getattr(message, "content", []):
        if getattr(item, "type", "") == "text":
            text_value = getattr(getattr(item, "text", None), "value", "")
            if text_value:
                chunks.append(text_value)
    return "\n".join(chunks).strip()


def wait_for_run_completion(client: OpenAI, thread_id: str, run_id: str, timeout_sec: int = 90):
    start = time.time()
    while True:
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run.status in ("completed", "failed", "cancelled", "expired", "requires_action"):
            return run
        if time.time() - start > timeout_sec:
            raise TimeoutError("Assistant run timed out.")
        time.sleep(1.0)


def ensure_thread(client: OpenAI, chat: Dict) -> str:
    if chat.get("thread_id"):
        return str(chat["thread_id"])
    thread = client.beta.threads.create()
    chat["thread_id"] = thread.id
    return thread.id


def ask_assistant(chat: Dict, user_message: str) -> str:
    client = get_client()
    assistant_id = get_assistant_id()
    thread_id = ensure_thread(client, chat)

    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message,
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    run = wait_for_run_completion(client, thread_id=thread_id, run_id=run.id)

    if run.status != "completed":
        raise RuntimeError(f"Assistant run ended with status: {run.status}")

    messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=20)
    for msg in messages.data:
        if msg.role == "assistant":
            text = extract_text_from_message(msg)
            if text:
                return text
    raise RuntimeError("No assistant response text found.")


def init_state():
    if "history" not in st.session_state:
        st.session_state.history = []
    if "active_chat_id" not in st.session_state:
        st.session_state.active_chat_id = None
    if "pending_input" not in st.session_state:
        st.session_state.pending_input = ""


def new_chat():
    chat_id = int(time.time() * 1000)
    chat = {
        "id": chat_id,
        "title": "Assistant Session",
        "thread_id": None,
        "updated_at": time.time(),
        "messages": [
            {
                "role": "assistant",
                "content": "こんにちは。アシスタント接続モードです。\nそのままメッセージを送信すると、接続済みAssistantに問い合わせます。",
            }
        ],
    }
    st.session_state.history.insert(0, chat)
    st.session_state.active_chat_id = chat_id


def get_active_chat() -> Optional[Dict]:
    active_id = st.session_state.active_chat_id
    for item in st.session_state.history:
        if item["id"] == active_id:
            return item
    return None


def get_chat_title_from_text(text: str) -> str:
    plain = text.strip().replace("\n", " ")
    if not plain:
        return "Assistant Session"
    return plain[:24] + ("..." if len(plain) > 24 else "")


def chat_css() -> str:
    return """
    <style>
      .stApp { background: #f3f4f6; }
      [data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }
      .main .block-container { max-width: 100%; padding: 0.75rem 1rem 1rem; }
      .panel {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 0.75rem;
      }
      .panel-title {
        font-size: 14px;
        font-weight: 600;
        color: #111827;
      }
      .rail {
        min-height: calc(100vh - 32px);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
      }
      .rail-top {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.65rem;
      }
      .icon {
        width: 42px;
        height: 42px;
        border-radius: 10px;
        background: #f3f4f6;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
      }
      .icon.active {
        background: #e5e7eb;
      }
      .avatar {
        width: 42px;
        height: 42px;
        border-radius: 999px;
        background: #e5e7eb;
      }
      .assistant-row {
        display: flex;
        gap: 0.65rem;
        margin-bottom: 0.75rem;
      }
      .assistant-icon {
        width: 34px;
        height: 34px;
        border-radius: 999px;
        background: #eef2ff;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }
      .assistant-name {
        font-size: 13px;
        font-weight: 600;
        color: #111827;
        margin-bottom: 4px;
      }
      .assistant-bubble {
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        border-top-left-radius: 4px;
        background: #fff;
        padding: 10px 12px;
        font-size: 14px;
        line-height: 1.6;
        color: #111827;
        white-space: pre-wrap;
      }
      .user-wrap {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 0.75rem;
      }
      .user-bubble {
        max-width: 80%;
        background: #111827;
        color: #fff;
        border-radius: 14px;
        border-top-right-radius: 4px;
        padding: 10px 12px;
        font-size: 14px;
        line-height: 1.6;
        white-space: pre-wrap;
      }
      .hint {
        font-size: 11px;
        color: #6b7280;
        display: flex;
        justify-content: space-between;
      }
      .thread-note {
        font-size: 11px;
        color: #6b7280;
        margin-top: 4px;
      }
      .stButton button {
        border-radius: 10px;
        border: 1px solid #d1d5db;
      }
      .stTextArea textarea {
        border-radius: 12px;
        border: 1px solid #d1d5db;
        min-height: 84px;
      }
    </style>
    """


def render_assistant_message(content: str):
    safe = escape(content).replace("\n", "<br>")
    st.markdown(
        f"""
        <div class="assistant-row">
          <div class="assistant-icon">✨</div>
          <div class="assistant-col">
            <div class="bot-name">AI Agent</div>
            <div class="chat-card"><div class="bot-msg">{safe}</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_user_message(content: str):
    safe = escape(content).replace("\n", "<br>")
    st.markdown(
        f'<div class="user-wrap"><div class="user-bubble">{safe}</div></div>',
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="セブン銀行 会話UI", page_icon="💬", layout="wide")
init_state()
if not st.session_state.history:
    new_chat()

st.markdown(chat_css(), unsafe_allow_html=True)

left, history_col, main_col = st.columns([0.08, 0.24, 0.68], gap="small")

with left:
    st.markdown(
        """
        <div class="panel rail">
          <div class="rail-top">
            <img src="https://deca-custom-nmcm-web.vercel.app/deca-x-logo.svg" width="40">
            <div class="icon">📊</div>
            <div class="icon active">🖱️</div>
            <div class="icon">⚙️</div>
          </div>
          <div style="display:flex; justify-content:center;">
            <div class="avatar"></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with history_col:
    st.markdown('<div class="panel-title">会話履歴</div>', unsafe_allow_html=True)
    h1, h2 = st.columns([0.72, 0.28])
    with h1:
        st.caption(f"{len(st.session_state.history)} chats")
    with h2:
        if st.button("新規", key="new_chat_side", use_container_width=True):
            new_chat()
            st.rerun()

    history_sorted = sorted(st.session_state.history, key=lambda x: x["updated_at"], reverse=True)
    for item in history_sorted:
        title = item["title"]
        thread_id = item["thread_id"] or "thread未作成"
        is_active = item["id"] == st.session_state.active_chat_id
        label = f"{'● ' if is_active else ''}{title}\n{thread_id}"
        if st.button(label, key=f"hist_{item['id']}", use_container_width=True, type="secondary"):
            st.session_state.active_chat_id = item["id"]
            st.rerun()

active_chat = get_active_chat()
if not active_chat:
    new_chat()
    active_chat = get_active_chat()

submitted = False
prompt = ""

with main_col:
    m1, m2 = st.columns([0.75, 0.25])
    with m1:
        st.markdown(f"<div class='panel-title'>{escape(active_chat['title'])}</div>", unsafe_allow_html=True)
    with m2:
        if st.button("新しい対話", key="new_chat_main", use_container_width=True):
            new_chat()
            st.rerun()

    msg_box = st.container(border=True)
    with msg_box:
        for msg in active_chat["messages"]:
            if msg["role"] == "user":
                render_user_message(msg["content"])
            else:
                render_assistant_message(msg["content"])

    with st.form("chat_form", clear_on_submit=True):
        prompt = st.text_area(
            "メッセージ",
            placeholder="例：『手数料無料！春の投資デビューキャンペーン』というバナーならクリックしますか？",
            label_visibility="collapsed",
        )
        c1, c2 = st.columns([0.78, 0.22])
        with c1:
            st.markdown(
                "<div class='hint'><span>Enterで送信 / Shift+Enterで改行</span><span>Mode: Assistant Connected</span></div>",
                unsafe_allow_html=True,
            )
        with c2:
            submitted = st.form_submit_button("送信", use_container_width=True)

    thread_id_note = active_chat.get("thread_id") or "未作成"
    st.markdown(f"<div class='thread-note'>Thread: {escape(str(thread_id_note))}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

if submitted and prompt.strip():
    text = prompt.strip()
    active_chat["messages"].append({"role": "user", "content": text})
    if active_chat["title"] == "Assistant Session":
        active_chat["title"] = get_chat_title_from_text(text)
    active_chat["updated_at"] = datetime.now().timestamp()
    try:
        with st.spinner("アシスタントへ問い合わせ中..."):
            reply = ask_assistant(active_chat, text)
        active_chat["messages"].append({"role": "assistant", "content": reply})
    except Exception as exc:
        active_chat["messages"].append({"role": "assistant", "content": f"エラー: {exc}"})
    active_chat["updated_at"] = datetime.now().timestamp()
    st.rerun()
