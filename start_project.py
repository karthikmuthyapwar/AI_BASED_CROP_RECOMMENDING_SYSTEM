#!/usr/bin/env python3
"""Start backend and frontend servers together for local development."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_PORT = 8000
FRONTEND_PORT = 5500
MODEL_PATH = ROOT / "backend" / "app" / "model" / "model.pkl"


def start_process(command: list[str], name: str) -> subprocess.Popen:
    print(f"[start] {name}: {' '.join(command)}")
    return subprocess.Popen(command, cwd=ROOT)


def stop_process(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    print(f"[stop] {name}")
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def ensure_model() -> None:
    if MODEL_PATH.exists():
        return
    print(f"[setup] Model not found at {MODEL_PATH}. Training model...")
    train_cmd = [sys.executable, "scripts/train_model.py"]
    completed = subprocess.run(train_cmd, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError("Model training failed. Please run scripts/train_model.py manually.")
    if not MODEL_PATH.exists():
        raise RuntimeError(f"Training completed but model file is still missing at {MODEL_PATH}.")


def main() -> int:
    ensure_model()

    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--reload",
        "--port",
        str(BACKEND_PORT),
    ]
    frontend_cmd = [
        sys.executable,
        "-m",
        "http.server",
        str(FRONTEND_PORT),
        "--directory",
        "frontend",
    ]

    backend = start_process(backend_cmd, "backend")
    frontend = start_process(frontend_cmd, "frontend")

    def shutdown(_signum: int | None = None, _frame: object | None = None) -> None:
        stop_process(frontend, "frontend")
        stop_process(backend, "backend")

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    url = f"http://localhost:{FRONTEND_PORT}"
    print(f"[info] Opening {url} ...")
    webbrowser.open(url)

    try:
        while True:
            if backend.poll() is not None:
                print("[error] Backend process exited.")
                return backend.returncode or 1
            if frontend.poll() is not None:
                print("[error] Frontend process exited.")
                return frontend.returncode or 1
            time.sleep(1)
    finally:
        shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
