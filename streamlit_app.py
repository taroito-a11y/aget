import os
import time

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


def ensure_thread(client: OpenAI) -> str:
    if st.session_state.thread_id:
        return st.session_state.thread_id
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id
    return thread.id


def ask_assistant(user_message: str) -> str:
    client = get_client()
    assistant_id = get_assistant_id()
    thread_id = ensure_thread(client)

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


st.set_page_config(page_title="セブン銀行 会話UI", page_icon="💬", layout="centered")
st.title("セブン銀行 会話型UI")
st.caption("OpenAI Assistants API 連携")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("新しい対話を開始", use_container_width=True):
        st.session_state.thread_id = None
        st.session_state.messages = []
        st.rerun()
with col2:
    st.info(f"Thread: {st.session_state.thread_id or '未作成'}")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("メッセージを入力")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("アシスタントに問い合わせ中..."):
                reply = ask_assistant(prompt)
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
        except Exception as exc:
            error_text = f"エラー: {exc}"
            st.error(error_text)
            st.session_state.messages.append({"role": "assistant", "content": error_text})
