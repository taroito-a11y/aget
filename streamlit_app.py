import os
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from openai import OpenAI


load_dotenv()

APP_DIR = Path(__file__).resolve().parent
DEFAULT_ASSISTANT_ID = "asst_CJffYUKAcUgyYHaDbroFkLEE"

app = Flask(__name__)
CORS(app)


def _get_html_filename() -> str:
    # Handle Unicode normalization differences in local file names.
    matches = sorted(APP_DIR.glob("*管理画面*v2.html"))
    if matches:
        return matches[0].name
    return "セブン銀行会話型UI管理画面イメージv2.html"


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)


def _get_assistant_id() -> str:
    return os.getenv("OPENAI_ASSISTANT_ID", DEFAULT_ASSISTANT_ID).strip()


def _extract_text_from_message(message) -> str:
    chunks = []
    for item in getattr(message, "content", []):
        if getattr(item, "type", "") == "text":
            text_value = getattr(getattr(item, "text", None), "value", "")
            if text_value:
                chunks.append(text_value)
    return "\n".join(chunks).strip()


def _wait_for_run_completion(client: OpenAI, thread_id: str, run_id: str, timeout_sec: int = 90):
    start = time.time()
    while True:
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run.status in ("completed", "failed", "cancelled", "expired", "requires_action"):
            return run
        if time.time() - start > timeout_sec:
            raise TimeoutError("Assistant run timed out.")
        time.sleep(1.0)


@app.get("/")
def index():
    return send_from_directory(APP_DIR, _get_html_filename())


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/chat/start")
def chat_start():
    try:
        client = _get_client()
        thread = client.beta.threads.create()
        return jsonify({"thread_id": thread.id})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/chat/message")
def chat_message():
    data = request.get_json(silent=True) or {}
    thread_id = (data.get("thread_id") or "").strip()
    message = (data.get("message") or "").strip()

    if not thread_id:
        return jsonify({"error": "thread_id is required"}), 400
    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        client = _get_client()
        assistant_id = _get_assistant_id()

        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message,
        )

        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
        )

        run = _wait_for_run_completion(client, thread_id=thread_id, run_id=run.id)
        if run.status != "completed":
            return (
                jsonify(
                    {
                        "error": f"Assistant run ended with status: {run.status}",
                        "status": run.status,
                    }
                ),
                500,
            )

        messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=20)
        for msg in messages.data:
            if msg.role == "assistant":
                text = _extract_text_from_message(msg)
                if text:
                    return jsonify({"reply": text, "run_id": run.id})

        return jsonify({"error": "No assistant response text found."}), 500
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)
