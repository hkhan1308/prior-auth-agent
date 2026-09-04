"""
Phase 3 -- Agent loop: simulated external systems (tools).

These stand in for real downstream systems a production agent would call
over a network (a payer eligibility API, an imaging archive, a document
store). They're built to fail on command, on purpose: real external
systems are unreliable, and the point of this phase is wiring the Phase 1
reliability layer into real call sites, not assuming the happy path.

Each tool takes an optional `fail_mode` for deterministic testing:
    None        -- normal behavior
    "timeout"   -- raises TimeoutError, simulating a hung network call
    "malformed" -- returns a dict missing expected keys, simulating a
                   downstream system that responds but with garbage

This file is provided as-is -- it's the simulated world your agent loop
operates in, not the thing being learned. loop.py is where the actual
work happens.
"""
from typing import Optional, TypedDict


class EligibilityResult(TypedDict):
    eligible: bool
    plan_type: str
    payer_id: str


class ImagingHistoryResult(TypedDict):
    has_prior_imaging: bool
    most_recent_date: Optional[str]


class ClinicalNotesResult(TypedDict):
    notes_text: str
    author_npi: str


def fetch_eligibility(
    patient_id: str, payer_id: str, fail_mode: Optional[str] = None
) -> EligibilityResult:
    if fail_mode == "timeout":
        raise TimeoutError(f"eligibility check for {patient_id} timed out")
    if fail_mode == "malformed":
        return {"eligible": True}  # type: ignore[typeddict-item]  # missing keys, on purpose
    return {"eligible": True, "plan_type": "PPO", "payer_id": payer_id}


def fetch_prior_imaging(
    patient_id: str, procedure_code: str, fail_mode: Optional[str] = None
) -> ImagingHistoryResult:
    if fail_mode == "timeout":
        raise TimeoutError(f"imaging history lookup for {patient_id} timed out")
    if fail_mode == "malformed":
        return {"has_prior_imaging": "yes"}  # type: ignore[typeddict-item]  # wrong type, on purpose
    return {"has_prior_imaging": False, "most_recent_date": None}


def fetch_clinical_notes(
    patient_id: str, fail_mode: Optional[str] = None
) -> ClinicalNotesResult:
    if fail_mode == "timeout":
        raise TimeoutError(f"clinical notes fetch for {patient_id} timed out")
    if fail_mode == "malformed":
        return {}  # type: ignore[typeddict-item]  # empty, on purpose
    return {
        "notes_text": "Patient reports chronic headache, onset age 54, no prior imaging on file.",
        "author_npi": "1234567893",
    }
