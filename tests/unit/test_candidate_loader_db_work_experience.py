import json
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import database
from app.config import settings
from app.services.candidate_loader import get_profile_json, load_candidates


def _run_coro_in_thread(coro):
    result: dict[str, object] = {}

    def _target():
        import asyncio

        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:  # propagate to test thread
            result["error"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]  # type: ignore[misc]
    return result.get("value")


def test_startup_load_candidates_stores_and_uses_db_work_experience(tmp_path: Path):
    source_path = Path("data/candidates/phil_tillman.json")
    source_data = json.loads(source_path.read_text(encoding="utf-8"))
    data_dir = tmp_path / "candidates"
    data_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = data_dir / "phil_tillman.json"
    candidate_path.write_text(json.dumps(source_data), encoding="utf-8")

    db_path = tmp_path / "cvbot-test.db"
    original_db_path = settings.db_path
    original_data_dir = settings.data_dir

    async def _run():
        settings.db_path = str(db_path)
        settings.data_dir = str(data_dir)
        database._db = None
        await database.init_db()

        try:
            await load_candidates()
            db = await database.get_db()

            rows = await db.execute_fetchall(
                "SELECT id, first_name, last_name, middle_name, work_experience FROM candidates"
            )
            assert len(rows) == 1
            assert rows[0]["id"] == "phil_tillman"
            assert rows[0]["first_name"] == "Phil"
            assert rows[0]["last_name"] == "Tillman"
            assert rows[0]["middle_name"] is None

            db_json = json.loads(rows[0]["work_experience"])
            assert db_json["summary"] == source_data["summary"]

            replacement = {
                "summary": "from db",
                "skills": "",
                "work": [],
                "education": [],
                "publications": [],
            }
            await db.execute(
                "UPDATE candidates SET work_experience = ? WHERE id = ?",
                (json.dumps(replacement), "phil_tillman"),
            )
            await db.commit()

            await load_candidates()
            rows_after = await db.execute_fetchall("SELECT id FROM candidates")
            assert len(rows_after) == 1
            assert json.loads(get_profile_json("phil_tillman"))["summary"] == "from db"
        finally:
            if database._db is not None:
                await database._db.close()
                database._db = None

    try:
        _run_coro_in_thread(_run())
    finally:
        settings.db_path = original_db_path
        settings.data_dir = original_data_dir
