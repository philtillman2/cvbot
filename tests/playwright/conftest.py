import json
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest
from playwright.sync_api import Browser, sync_playwright

TEST_CANDIDATE_ID = "philip_j_fry"
SOURCE_JSON_PATH = Path("data/candidates/phil_tillman.json")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def playwright_test_candidate():
    payload = json.loads(SOURCE_JSON_PATH.read_text(encoding="utf-8"))
    with sqlite3.connect("cvbot.db") as conn:
        conn.execute(
            "INSERT OR REPLACE INTO candidates (id, first_name, last_name, middle_name, work_experience) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                TEST_CANDIDATE_ID,
                payload.get("first_name", ""),
                payload.get("last_name", ""),
                payload.get("middle_name"),
                json.dumps(payload),
            ),
        )
        conn.commit()
    try:
        yield
    finally:
        with sqlite3.connect("cvbot.db") as conn:
            conn.execute("DELETE FROM candidates WHERE id = ?", (TEST_CANDIDATE_ID,))
            conn.commit()


@pytest.fixture(scope="session")
def base_url(playwright_test_candidate) -> str:
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with urlopen(f"http://127.0.0.1:{port}/chat", timeout=1):
                    break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Timed out waiting for app server to start")
        yield f"http://127.0.0.1:{port}"
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


@pytest.fixture(scope="session")
def browser() -> Browser:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()
