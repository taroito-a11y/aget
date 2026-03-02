import os
import time
from datetime import datetime
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


def get_chat_title_from_text(text: str) -> str:
    plain = text.strip().replace("\n", " ")
    if not plain:
        return "Assistant Session"
    return plain[:24] + ("..." if len(plain) > 24 else "")


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
                "content": "こんにちは。メッセージを入力すると、Assistant に問い合わせます。",
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


st.set_page_config(page_title="セブン銀行 会話UI", page_icon="💬", layout="wide")
init_state()
if not st.session_state.history:
    new_chat()

with st.sidebar:
    st.title("会話履歴")
    if st.button("＋ 新しい対話", use_container_width=True):
        new_chat()
        st.rerun()

    st.divider()
    history_sorted = sorted(st.session_state.history, key=lambda x: x["updated_at"], reverse=True)
    for item in history_sorted:
        is_active = item["id"] == st.session_state.active_chat_id
        marker = "● " if is_active else ""
        if st.button(f"{marker}{item['title']}", key=f"hist_{item['id']}", use_container_width=True):
            st.session_state.active_chat_id = item["id"]
            st.rerun()

active_chat = get_active_chat()
if not active_chat:
    new_chat()
    active_chat = get_active_chat()

header_col1, header_col2 = st.columns([0.8, 0.2])
with header_col1:
    st.subheader(active_chat["title"])
with header_col2:
    if st.button("新しい対話", use_container_width=True):
        new_chat()
        st.rerun()

thread_id_note = active_chat.get("thread_id") or "未作成"
st.caption(f"Mode: Assistant Connected | Thread: {thread_id_note}")
st.divider()

for msg in active_chat["messages"]:
    role = "assistant" if msg["role"] != "user" else "user"
    with st.chat_message(role):
        st.markdown(msg["content"])

prompt = st.chat_input("メッセージを入力（Enterで送信）")
if prompt and prompt.strip():
    text = prompt.strip()
    active_chat["messages"].append({"role": "user", "content": text})
    if active_chat["title"] == "Assistant Session":
        active_chat["title"] = get_chat_title_from_text(text)
    active_chat["updated_at"] = datetime.now().timestamp()

    with st.chat_message("assistant"):
        try:
            with st.spinner("アシスタントへ問い合わせ中..."):
                reply = ask_assistant(active_chat, text)
            st.markdown(reply)
            active_chat["messages"].append({"role": "assistant", "content": reply})
        except Exception as exc:
            error_text = f"エラー: {exc}"
            st.error(error_text)
            active_chat["messages"].append({"role": "assistant", "content": error_text})

    active_chat["updated_at"] = datetime.now().timestamp()
    st.rerun()
