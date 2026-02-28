import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models import Candidate


def test_phil_tillman_json_matches_expected_schema():
    payload = json.loads(Path("data/candidates/phil_tillman.json").read_text(encoding="utf-8"))

    assert set(payload.keys()) == {
        "first_name",
        "middle_name",
        "last_name",
        "location",
        "work_experience",
    }
    assert set(payload["location"].keys()) == {"city", "country"}

    we = payload["work_experience"]
    assert set(we.keys()) == {"summary", "skills", "work", "education", "publications"}

    assert isinstance(we["work"], list)
    assert isinstance(we["education"], list)
    assert isinstance(we["publications"], list)
    assert we["work"], "Expected at least one work entry"
    assert we["education"], "Expected at least one education entry"

    first_work = we["work"][0]
    assert set(first_work.keys()) == {"start", "end", "employer", "roles"}
    assert set(first_work["start"].keys()) == {"year", "month"}
    assert "present" in first_work["end"] or {"year", "month"}.issubset(first_work["end"].keys())
    assert {"name", "description", "link", "sector", "location"}.issubset(first_work["employer"].keys())

    Candidate.model_validate(payload)
