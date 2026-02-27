"""Tests for contact-form spam protections."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from conftest import UnitTestEnv, _run_coro_in_thread


def _contact_payload(*, started_at: int | None = None, website: str = "", turnstile: str = ""):
    return {
        "name": "Test User",
        "email": "test@example.com",
        "subject": "Hello",
        "message": "This is a test message",
        "website": website,
        "form_started_at": str(started_at if started_at is not None else int(time.time()) - 10),
        "cf-turnstile-response": turnstile,
    }


def test_contact_honeypot_blocks_submission(tmp_path: Path, test_candidate_source_data, monkeypatch):
    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.main import app
            from app.routers import contact

            sent = {"called": False}

            def _fake_send_contact_email(**_kwargs):
                sent["called"] = True

            monkeypatch.setattr(contact, "send_contact_email", _fake_send_contact_email)

            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/contact", data=_contact_payload(website="https://spam.example"))
                assert resp.status_code == 400
                assert "Unable to send message. Please try again." in resp.text
                assert sent["called"] is False

    _run_coro_in_thread(_run())


def test_contact_min_submit_time_blocks_fast_submit(tmp_path: Path, test_candidate_source_data, monkeypatch):
    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.config import settings
            from app.main import app
            from app.routers import contact

            monkeypatch.setattr(settings, "contact_min_submit_time_enabled", True)
            monkeypatch.setattr(settings, "contact_min_submit_time_seconds", 5)
            monkeypatch.setattr(settings, "contact_turnstile_enabled", False)

            sent = {"called": False}

            def _fake_send_contact_email(**_kwargs):
                sent["called"] = True

            monkeypatch.setattr(contact, "send_contact_email", _fake_send_contact_email)

            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/contact", data=_contact_payload(started_at=int(time.time())))
                assert resp.status_code == 400
                assert "Please wait a moment before sending." in resp.text
                assert sent["called"] is False

    _run_coro_in_thread(_run())


def test_contact_min_submit_time_disabled_allows_fast_submit(tmp_path: Path, test_candidate_source_data, monkeypatch):
    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.config import settings
            from app.main import app
            from app.routers import contact

            monkeypatch.setattr(settings, "contact_min_submit_time_enabled", False)
            monkeypatch.setattr(settings, "contact_turnstile_enabled", False)

            sent = {"called": False}

            def _fake_send_contact_email(**_kwargs):
                sent["called"] = True

            monkeypatch.setattr(contact, "send_contact_email", _fake_send_contact_email)

            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/contact", data=_contact_payload(started_at=int(time.time())))
                assert resp.status_code == 200
                assert "Thanks, your message was sent." in resp.text
                assert sent["called"] is True

    _run_coro_in_thread(_run())


def test_contact_turnstile_required_when_enabled(tmp_path: Path, test_candidate_source_data, monkeypatch):
    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.config import settings
            from app.main import app
            from app.routers import contact

            monkeypatch.setattr(settings, "contact_turnstile_enabled", True)
            monkeypatch.setattr(settings, "contact_min_submit_time_enabled", False)

            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/contact", data=_contact_payload(turnstile=""))
                assert resp.status_code == 400
                assert "Please complete the verification challenge." in resp.text

            async def _fake_verify_turnstile_token(_token: str, _remote_ip: str | None):
                return False

            monkeypatch.setattr(contact, "_verify_turnstile_token", _fake_verify_turnstile_token)
            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/contact", data=_contact_payload(turnstile="bad-token"))
                assert resp.status_code == 400
                assert "Verification challenge failed. Please try again." in resp.text

    _run_coro_in_thread(_run())


def test_contact_turnstile_valid_token_allows_submit(tmp_path: Path, test_candidate_source_data, monkeypatch):
    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.config import settings
            from app.main import app
            from app.routers import contact

            monkeypatch.setattr(settings, "contact_turnstile_enabled", True)
            monkeypatch.setattr(settings, "contact_min_submit_time_enabled", False)

            async def _fake_verify_turnstile_token(_token: str, _remote_ip: str | None):
                return True

            monkeypatch.setattr(contact, "_verify_turnstile_token", _fake_verify_turnstile_token)

            sent = {"called": False}

            def _fake_send_contact_email(**_kwargs):
                sent["called"] = True

            monkeypatch.setattr(contact, "send_contact_email", _fake_send_contact_email)

            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/contact", data=_contact_payload(turnstile="good-token"))
                assert resp.status_code == 200
                assert sent["called"] is True

    _run_coro_in_thread(_run())
