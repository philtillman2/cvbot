"""Shared fixtures and utilities for unit tests.

Global setup adds a test user ``philip_j_fry`` (using phil_tillman.json data).
Global teardown deletes the user and closes the DB.
"""

import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import database
from app.config import settings
from app.services.candidate_loader import load_candidates

TEST_CANDIDATE_ID = "philip_j_fry"
SOURCE_JSON_PATH = Path("data/candidates/phil_tillman.json")


def _run_coro_in_thread(coro):
    """Run an async coroutine in a fresh event loop on a dedicated thread."""
    result: dict[str, object] = {}

    def _target():
        import asyncio

        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]  # type: ignore[misc]
    return result.get("value")


class UnitTestEnv:
    """Async context manager: sets up a temp DB with philip_j_fry, tears down after."""

    def __init__(self, tmp_path: Path, source_data: dict):
        self._tmp_path = tmp_path
        self._source_data = source_data
        self._orig_db = settings.db_path
        self._orig_data = settings.data_dir

    async def __aenter__(self):
        data_dir = self._tmp_path / "candidates"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / f"{TEST_CANDIDATE_ID}.json").write_text(
            json.dumps(self._source_data), encoding="utf-8"
        )
        settings.db_path = str(self._tmp_path / "test.db")
        settings.data_dir = str(data_dir)
        database._db = None
        await database.init_db()
        await load_candidates()
        return self

    async def __aexit__(self, *exc):
        if database._db is not None:
            db = await database.get_db()
            await db.execute(
                "DELETE FROM candidates WHERE id = ?", (TEST_CANDIDATE_ID,)
            )
            await db.commit()
            await database._db.close()
            database._db = None
        settings.db_path = self._orig_db
        settings.data_dir = self._orig_data


@pytest.fixture(scope="session")
def test_candidate_source_data():
    """Load phil_tillman.json once per session as the canonical test data."""
    return json.loads(SOURCE_JSON_PATH.read_text(encoding="utf-8"))
