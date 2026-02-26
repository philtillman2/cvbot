import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.models import WorkExperience


def test_philip_j_fry_json_serialization_round_trip(test_candidate_source_data):
    model = WorkExperience.model_validate(test_candidate_source_data)
    serialized_json = model.model_dump_json()
    reparsed = WorkExperience.model_validate_json(serialized_json)

    assert reparsed == model
