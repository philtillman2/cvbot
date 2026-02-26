"""Tests for the inline-editable work experience feature.

Covers:
- GET /work-experience serves page with embedded profile JSON
- PUT /api/candidates/{id}/work-experience saves and persists edits
- PUT validates payload via WorkExperience (rejects invalid data)
- PUT returns 404 for unknown candidate
- save_profile updates both DB and in-memory cache
- Adding / removing array items round-trips correctly
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import database
from app.models import WorkExperience
from app.services.candidate_loader import (
    get_profile,
    get_profile_json,
    save_profile,
)
from conftest import TEST_CANDIDATE_ID, UnitTestEnv, _run_coro_in_thread


# ─── Tests ────────────────────────────────────────────────────


def test_get_work_experience_page_contains_profile_json(
    tmp_path: Path, test_candidate_source_data
):
    """GET /work-experience should embed __profileData in the HTML."""
    source_data = test_candidate_source_data

    async def _run():
        async with UnitTestEnv(tmp_path, source_data):
            import httpx
            from httpx import ASGITransport
            from app.main import app

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    f"/work-experience?candidate_id={TEST_CANDIDATE_ID}"
                )
                assert resp.status_code == 200
                assert "window.__profileData" in resp.text
                assert "work_experience.js" in resp.text
                assert source_data["summary"][:40] in resp.text

    _run_coro_in_thread(_run())


def test_put_saves_and_persists_edits(tmp_path: Path, test_candidate_source_data):
    """PUT should update in-memory cache and DB."""

    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.main import app

            profile = get_profile(TEST_CANDIDATE_ID)
            d = profile.model_dump()
            d["summary"] = "Edited summary"
            d["skills"] = "Edited skills"

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.put(
                    f"/api/candidates/{TEST_CANDIDATE_ID}/work-experience", json=d
                )
                assert resp.status_code == 200
                assert resp.json() == {"ok": True}

            # In-memory cache updated
            updated = get_profile(TEST_CANDIDATE_ID)
            assert updated.summary == "Edited summary"
            assert updated.skills == "Edited skills"

            # DB persisted
            db = await database.get_db()
            rows = await db.execute_fetchall(
                "SELECT work_experience FROM candidates WHERE id = ?",
                (TEST_CANDIDATE_ID,),
            )
            db_data = json.loads(rows[0]["work_experience"])
            assert db_data["summary"] == "Edited summary"

    _run_coro_in_thread(_run())


def test_put_rejects_invalid_payload(tmp_path: Path, test_candidate_source_data):
    """PUT with an invalid body should return 422."""

    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.main import app

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # work entries require employer with a name (str, not int)
                bad = {
                    "summary": "ok",
                    "skills": "ok",
                    "work": [{"start": "not-a-date", "end": {}, "employer": 123}],
                    "education": [],
                    "publications": [],
                }
                resp = await client.put(
                    f"/api/candidates/{TEST_CANDIDATE_ID}/work-experience", json=bad
                )
                assert resp.status_code == 422

    _run_coro_in_thread(_run())


def test_put_returns_404_for_unknown_candidate(
    tmp_path: Path, test_candidate_source_data
):
    """PUT for a non-existent candidate should return 404."""

    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.main import app

            payload = WorkExperience(summary="x").model_dump()
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.put(
                    "/api/candidates/nonexistent/work-experience", json=payload
                )
                assert resp.status_code == 404

    _run_coro_in_thread(_run())


def test_save_profile_updates_db_and_cache(
    tmp_path: Path, test_candidate_source_data
):
    """save_profile() should update both in-memory cache and DB row."""

    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            original = get_profile(TEST_CANDIDATE_ID)
            assert original is not None

            modified = original.model_copy(
                update={"summary": "new summary via save_profile"}
            )
            await save_profile(TEST_CANDIDATE_ID, modified)

            assert (
                get_profile(TEST_CANDIDATE_ID).summary
                == "new summary via save_profile"
            )
            assert "new summary via save_profile" in get_profile_json(
                TEST_CANDIDATE_ID
            )

            db = await database.get_db()
            rows = await db.execute_fetchall(
                "SELECT work_experience FROM candidates WHERE id = ?",
                (TEST_CANDIDATE_ID,),
            )
            assert "new summary via save_profile" in rows[0]["work_experience"]

    _run_coro_in_thread(_run())


def test_put_add_and_remove_work_entry(
    tmp_path: Path, test_candidate_source_data
):
    """Adding a work entry then removing it should round-trip correctly."""

    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.main import app

            profile = get_profile(TEST_CANDIDATE_ID)
            d = profile.model_dump()
            original_count = len(d["work"])

            # Add a work entry
            d["work"].append({
                "start": {"year": 2025, "month": 1},
                "end": {"present": True},
                "employer": {
                    "name": "Test Corp",
                    "description": "",
                    "link": "",
                    "sector": "Tech",
                    "location": "Remote",
                },
                "roles": [{
                    "start": {"year": 2025, "month": 1},
                    "end": {"present": True},
                    "title": "Engineer",
                    "employment_type": "Full time",
                    "items": [{"title": "Item1", "description": "Desc", "contribution": "Contrib"}],
                }],
            })

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.put(
                    f"/api/candidates/{TEST_CANDIDATE_ID}/work-experience",
                    json=d,
                )
                assert resp.status_code == 200

            updated = get_profile(TEST_CANDIDATE_ID)
            assert len(updated.work) == original_count + 1
            assert updated.work[-1].employer.name == "Test Corp"
            assert updated.work[-1].roles[0].items[0].title == "Item1"

            # Remove the added entry
            d2 = updated.model_dump()
            d2["work"].pop()

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp2 = await client.put(
                    f"/api/candidates/{TEST_CANDIDATE_ID}/work-experience",
                    json=d2,
                )
                assert resp2.status_code == 200

            restored = get_profile(TEST_CANDIDATE_ID)
            assert len(restored.work) == original_count

    _run_coro_in_thread(_run())


def test_put_add_and_remove_education_subject(
    tmp_path: Path, test_candidate_source_data
):
    """Adding/removing a subject in education should persist correctly."""

    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.main import app

            profile = get_profile(TEST_CANDIDATE_ID)
            d = profile.model_dump()
            original_subjects = list(d["education"][0]["subjects"])

            d["education"][0]["subjects"].append("New Subject")

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.put(
                    f"/api/candidates/{TEST_CANDIDATE_ID}/work-experience",
                    json=d,
                )
                assert resp.status_code == 200

            updated = get_profile(TEST_CANDIDATE_ID)
            assert "New Subject" in updated.education[0].subjects

            # Remove it
            d2 = updated.model_dump()
            d2["education"][0]["subjects"].remove("New Subject")

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp2 = await client.put(
                    f"/api/candidates/{TEST_CANDIDATE_ID}/work-experience",
                    json=d2,
                )
                assert resp2.status_code == 200

            restored = get_profile(TEST_CANDIDATE_ID)
            assert restored.education[0].subjects == original_subjects

    _run_coro_in_thread(_run())


def test_put_add_and_remove_publication_author(
    tmp_path: Path, test_candidate_source_data
):
    """Adding/removing an author on a publication should persist correctly."""

    async def _run():
        async with UnitTestEnv(tmp_path, test_candidate_source_data):
            import httpx
            from httpx import ASGITransport
            from app.main import app

            profile = get_profile(TEST_CANDIDATE_ID)
            d = profile.model_dump()
            original_authors = len(d["publications"][0]["authors"])

            d["publications"][0]["authors"].append(
                {"first_name": "Test", "last_name": "Author"}
            )

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.put(
                    f"/api/candidates/{TEST_CANDIDATE_ID}/work-experience",
                    json=d,
                )
                assert resp.status_code == 200

            updated = get_profile(TEST_CANDIDATE_ID)
            assert len(updated.publications[0].authors) == original_authors + 1
            assert updated.publications[0].authors[-1].last_name == "Author"

            # Remove the added author
            d2 = updated.model_dump()
            d2["publications"][0]["authors"].pop()

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp2 = await client.put(
                    f"/api/candidates/{TEST_CANDIDATE_ID}/work-experience",
                    json=d2,
                )
                assert resp2.status_code == 200

            restored = get_profile(TEST_CANDIDATE_ID)
            assert len(restored.publications[0].authors) == original_authors

    _run_coro_in_thread(_run())
