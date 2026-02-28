import json
from pathlib import Path

from app.config import settings
from app.database import get_db
from app.models import Candidate, WorkExperience

# In-memory cache: candidate_id -> Candidate
_candidates: dict[str, Candidate] = {}
_profile_json: dict[str, str] = {}


def _slug_to_name_parts(slug: str) -> tuple[str, str, str | None]:
    parts = slug.replace("_", " ").replace(".", " ").replace("-", " ").split()
    titled = [part.title() for part in parts]
    if not titled:
        return "Unknown", "Candidate", None
    if len(titled) == 1:
        return titled[0], titled[0], None
    if len(titled) == 2:
        return titled[0], titled[1], None
    return titled[0], titled[-1], " ".join(titled[1:-1])


def _candidate_to_name_parts(candidate: Candidate) -> tuple[str, str, str | None] | None:
    first_name = (candidate.first_name or "").strip()
    last_name = (candidate.last_name or "").strip()
    middle_name = (candidate.middle_name or "").strip()
    if not first_name or not last_name:
        return None
    return first_name, last_name, middle_name or None


def _candidate_from_json(raw_json: str) -> Candidate:
    payload = json.loads(raw_json)
    if "work_experience" in payload:
        return Candidate.model_validate(payload)
    legacy_profile = WorkExperience.model_validate(payload)
    return Candidate(work_experience=legacy_profile)


async def load_candidates():
    """Scan data directory for candidate JSON files and register them."""
    _candidates.clear()
    _profile_json.clear()
    data_dir = Path(settings.data_dir)

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, work_experience FROM candidates WHERE work_experience IS NOT NULL"
    )
    for row in rows:
        candidate = _candidate_from_json(row["work_experience"])
        _candidates[row["id"]] = candidate
        _profile_json[row["id"]] = candidate.model_dump_json()

    existing_rows = await db.execute_fetchall("SELECT id, work_experience FROM candidates")
    existing_ids = {row["id"] for row in existing_rows}
    existing_with_work = {row["id"] for row in existing_rows if row["work_experience"]}

    if not data_dir.exists():
        return

    for path in sorted(data_dir.glob("*.json")):
        candidate_id = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))

        candidate = Candidate.model_validate(data)
        work_experience_json = candidate.model_dump_json()

        name_parts = _candidate_to_name_parts(candidate)
        if name_parts is None:
            name_parts = _slug_to_name_parts(candidate_id)
        first_name, last_name, middle_name = name_parts
        if candidate_id in existing_ids:
            work_experience_to_store = work_experience_json
            candidate_to_cache = candidate
            if candidate_id in existing_with_work:
                existing_candidate = _candidates[candidate_id]
                candidate_to_cache = existing_candidate
                needs_metadata_update = (
                    (not existing_candidate.first_name and bool(candidate.first_name))
                    or (not existing_candidate.middle_name and bool(candidate.middle_name))
                    or (not existing_candidate.last_name and bool(candidate.last_name))
                    or (existing_candidate.location is None and candidate.location is not None)
                )
                if needs_metadata_update:
                    candidate_to_cache = existing_candidate.model_copy(
                        update={
                            "first_name": candidate.first_name or existing_candidate.first_name,
                            "middle_name": candidate.middle_name or existing_candidate.middle_name,
                            "last_name": candidate.last_name or existing_candidate.last_name,
                            "location": candidate.location or existing_candidate.location,
                        }
                    )
                work_experience_to_store = candidate_to_cache.model_dump_json()

            await db.execute(
                "UPDATE candidates SET first_name = ?, last_name = ?, middle_name = ?, work_experience = ? "
                "WHERE id = ?",
                (
                    first_name,
                    last_name,
                    middle_name,
                    work_experience_to_store,
                    candidate_id,
                ),
            )
            _candidates[candidate_id] = candidate_to_cache
            _profile_json[candidate_id] = work_experience_to_store
        else:
            await db.execute(
                "INSERT INTO candidates (id, first_name, last_name, middle_name, work_experience) "
                "VALUES (?, ?, ?, ?, ?)",
                (candidate_id, first_name, last_name, middle_name, work_experience_json),
            )
            _candidates[candidate_id] = candidate
            _profile_json[candidate_id] = work_experience_json
    await db.commit()


def get_candidate(candidate_id: str) -> Candidate | None:
    return _candidates.get(candidate_id)


def get_candidate_json(candidate_id: str) -> str | None:
    return _profile_json.get(candidate_id)


async def save_candidate(candidate_id: str, candidate: Candidate) -> None:
    candidate_json = candidate.model_dump_json()
    db = await get_db()
    await db.execute(
        "UPDATE candidates SET work_experience = ? WHERE id = ?",
        (candidate_json, candidate_id),
    )
    await db.commit()
    _candidates[candidate_id] = candidate
    _profile_json[candidate_id] = candidate_json


def get_profile(candidate_id: str) -> WorkExperience | None:
    candidate = _candidates.get(candidate_id)
    return candidate.work_experience if candidate else None


def get_profile_json(candidate_id: str) -> str | None:
    return get_candidate_json(candidate_id)


async def save_profile(candidate_id: str, profile: WorkExperience) -> None:
    """Persist validated WorkExperience into a Candidate and update cache/DB."""
    existing = _candidates.get(candidate_id)
    if existing is None:
        raise ValueError(f"Candidate not found: {candidate_id}")
    updated = existing.model_copy(update={"work_experience": profile})
    await save_candidate(candidate_id, updated)
