"""
Phase 2 -- Ingestion: parse and validate a raw request.

Contract:
    parse_request(raw: dict) -> PriorAuthRequest

    - Valid input returns a populated PriorAuthRequest.
    - A missing required field raises IngestionError naming the missing
      field(s) -- "missing required field: provider_npi", not a bare
      "invalid input".
    - A procedure_code that isn't 5 digits (CPT format) raises
      IngestionError with a specific, actionable message naming the field
      and what's wrong with it.

This is the difference between a demo parser and a production one: the
error has to tell someone downstream (a human reviewer, a retry system,
a log) exactly what was wrong and where.

Not implemented. See tests/test_ingestion.py.
"""
from src.ingestion.models import PriorAuthRequest


class IngestionError(Exception):
    pass


def parse_request(raw: dict) -> PriorAuthRequest:
    raise NotImplementedError("Implement parse_request")
