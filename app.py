import os
import subprocess
import sys


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "streamlit_app.py",
        "--server.port",
        str(port),
        "--server.address",
        "0.0.0.0",
    ]
    raise SystemExit(subprocess.call(cmd))
