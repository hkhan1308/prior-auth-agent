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
"""


from src.ingestion.models import PriorAuthRequest
from pydantic import ValidationError

class IngestionError(Exception):
    pass


def parse_request(raw: dict) -> PriorAuthRequest:
    try:
        return PriorAuthRequest(**raw)
    except ValidationError as exc:
        messages = []
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"]) or "<request>"
            messages.append(f"{field}: {error['msg']}")
        raise IngestionError("; ".join(messages)) from exc
