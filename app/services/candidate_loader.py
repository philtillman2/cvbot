import json
from pathlib import Path

from app.config import settings
from app.database import get_db
from app.models import WorkExperience

# In-memory cache: candidate_id -> WorkExperience
_profiles: dict[str, WorkExperience] = {}
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


async def load_candidates():
    """Scan data directory for candidate JSON files and register them."""
    _profiles.clear()
    _profile_json.clear()
    data_dir = Path(settings.data_dir)

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, work_experience FROM candidates WHERE work_experience IS NOT NULL"
    )
    for row in rows:
        profile = WorkExperience.model_validate_json(row["work_experience"])
        _profiles[row["id"]] = profile
        _profile_json[row["id"]] = row["work_experience"]

    existing_rows = await db.execute_fetchall("SELECT id, work_experience FROM candidates")
    existing_ids = {row["id"] for row in existing_rows}
    existing_with_work = {row["id"] for row in existing_rows if row["work_experience"]}

    if not data_dir.exists():
        return

    for path in sorted(data_dir.glob("*.json")):
        candidate_id = path.stem
        if candidate_id in existing_with_work:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))

        profile = WorkExperience.model_validate(data)
        work_experience_json = profile.model_dump_json()
        _profiles[candidate_id] = profile
        _profile_json[candidate_id] = work_experience_json

        first_name, last_name, middle_name = _slug_to_name_parts(candidate_id)
        if candidate_id in existing_ids:
            await db.execute(
                "UPDATE candidates SET first_name = ?, last_name = ?, middle_name = ?, work_experience = ? "
                "WHERE id = ?",
                (first_name, last_name, middle_name, work_experience_json, candidate_id),
            )
        else:
            await db.execute(
                "INSERT INTO candidates (id, first_name, last_name, middle_name, work_experience) "
                "VALUES (?, ?, ?, ?, ?)",
                (candidate_id, first_name, last_name, middle_name, work_experience_json),
            )
    await db.commit()


def get_profile(candidate_id: str) -> WorkExperience | None:
    return _profiles.get(candidate_id)


def get_profile_json(candidate_id: str) -> str | None:
    return _profile_json.get(candidate_id)
