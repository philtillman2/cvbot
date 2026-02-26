"""Shared fixtures and utilities for unit tests.

Global setup adds a test user ``philip_j_fry`` (using phil_tillman.json data).
Global teardown deletes the user and closes the DB.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import database
from app.config import settings
from app.services.candidate_loader import load_candidates

TEST_CANDIDATE_ID = "philip_j_fry"
SOURCE_JSON_PATH = Path("data/candidates/phil_tillman.json")


@pytest.fixture(scope="session")
def test_candidate_source_data():
    """Load phil_tillman.json once per session as the canonical test data."""
    return json.loads(SOURCE_JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
async def test_env(tmp_path, test_candidate_source_data):
    """Set up a temp DB with philip_j_fry loaded, yield, then delete and tear down."""
    data_dir = tmp_path / "candidates"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / f"{TEST_CANDIDATE_ID}.json").write_text(
        json.dumps(test_candidate_source_data), encoding="utf-8"
    )

    orig_db = settings.db_path
    orig_data = settings.data_dir

    settings.db_path = str(tmp_path / "test.db")
    settings.data_dir = str(data_dir)
    database._db = None
    await database.init_db()
    await load_candidates()

    yield

    if database._db is not None:
        db = await database.get_db()
        await db.execute("DELETE FROM candidates WHERE id = ?", (TEST_CANDIDATE_ID,))
        await db.commit()
        await database._db.close()
        database._db = None
    settings.db_path = orig_db
    settings.data_dir = orig_data
