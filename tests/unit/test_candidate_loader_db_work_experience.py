import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import database
from app.services.candidate_loader import get_profile_json, load_candidates
from conftest import TEST_CANDIDATE_ID, UnitTestEnv, _run_coro_in_thread


def test_startup_load_candidates_stores_and_uses_db_work_experience(
    tmp_path: Path, test_candidate_source_data
):
    source_data = test_candidate_source_data

    async def _run():
        async with UnitTestEnv(tmp_path, source_data):
            db = await database.get_db()

            rows = await db.execute_fetchall(
                "SELECT id, first_name, last_name, middle_name, work_experience FROM candidates"
            )
            assert len(rows) == 1
            assert rows[0]["id"] == TEST_CANDIDATE_ID
            assert rows[0]["first_name"] == "Philip"
            assert rows[0]["last_name"] == "Tillman"
            assert rows[0]["middle_name"] == "Charles"

            db_json = json.loads(rows[0]["work_experience"])
            assert db_json["summary"] == source_data["summary"]
            assert db_json["profile"]["last_name"] == "Tillman"

            replacement = {
                "summary": "from db",
                "skills": "",
                "work": [],
                "education": [],
                "publications": [],
            }
            await db.execute(
                "UPDATE candidates SET work_experience = ? WHERE id = ?",
                (json.dumps(replacement), TEST_CANDIDATE_ID),
            )
            await db.commit()

            await load_candidates()
            rows_after = await db.execute_fetchall("SELECT id FROM candidates")
            assert len(rows_after) == 1
            profile_after = json.loads(get_profile_json(TEST_CANDIDATE_ID))
            assert profile_after["summary"] == "from db"
            assert profile_after["profile"]["last_name"] == "Tillman"

    _run_coro_in_thread(_run())
