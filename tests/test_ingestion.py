"""
Phase 2 tests. Define the contract for src/ingestion/parser.py.
"""
import json
from pathlib import Path

import pytest

from src.ingestion.parser import parse_request, IngestionError

DATA_DIR = Path(__file__).parent.parent / "data" / "sample_requests"


def load(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text())


def test_parses_valid_request():
    raw = load("valid_request.json")
    result = parse_request(raw)
    assert result.request_id == raw["request_id"]
    assert result.procedure_code == raw["procedure_code"]
    assert len(result.supporting_documents) == 1


def test_missing_field_raises_with_field_name():
    raw = load("missing_field_request.json")
    with pytest.raises(IngestionError) as exc_info:
        parse_request(raw)
    assert "provider_npi" in str(exc_info.value)


def test_malformed_procedure_code_raises_actionable_error():
    raw = load("malformed_procedure_code.json")
    with pytest.raises(IngestionError) as exc_info:
        parse_request(raw)
    assert "procedure_code" in str(exc_info.value)
