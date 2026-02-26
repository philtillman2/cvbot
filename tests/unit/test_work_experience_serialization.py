import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.models import WorkExperience


def test_phil_tillman_json_serialization_round_trip():
    candidate_file = Path("data/candidates/phil_tillman.json")
    source_json = candidate_file.read_text(encoding="utf-8")
    source_data = json.loads(source_json)

    model = WorkExperience.model_validate(source_data)
    serialized_json = model.model_dump_json()
    reparsed = WorkExperience.model_validate_json(serialized_json)

    assert reparsed == model
