import os

from streamlit_app import app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    debug = os.getenv("FLASK_DEBUG", "0").strip() == "1"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
