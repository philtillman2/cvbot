import json
from pathlib import Path

from app.config import settings
from app.database import get_db
from app.models import CandidateProfile

# In-memory cache: candidate_id -> CandidateProfile
_profiles: dict[str, CandidateProfile] = {}


def _slug_to_display_name(slug: str) -> str:
    return slug.replace("_", " ").replace(".", " ").title()


async def load_candidates():
    """Scan data directory for candidate JSON files and register them."""
    data_dir = Path(settings.data_dir)
    if not data_dir.exists():
        return

    db = await get_db()
    for path in sorted(data_dir.glob("*.json")):
        candidate_id = path.stem
        with open(path) as f:
            data = json.load(f)

        profile = CandidateProfile(**data)
        _profiles[candidate_id] = profile

        display_name = _slug_to_display_name(candidate_id)
        await db.execute(
            "INSERT OR REPLACE INTO candidates (id, display_name, json_path) VALUES (?, ?, ?)",
            (candidate_id, display_name, str(path)),
        )
    await db.commit()


def get_profile(candidate_id: str) -> CandidateProfile | None:
    return _profiles.get(candidate_id)


def get_profile_json(candidate_id: str) -> str | None:
    """Return the raw JSON string for injection into system prompt."""
    data_dir = Path(settings.data_dir)
    path = data_dir / f"{candidate_id}.json"
    if path.exists():
        return path.read_text()
    return None
