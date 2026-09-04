"""
Phase 3 tests. These define the contract for src/agent/loop.py.
Implement run_validation_loop against these -- don't edit the tests.
"""
import pytest

from src.agent.loop import AgentTools, ValidationResult, run_validation_loop
from src.ingestion.models import PriorAuthRequest, SupportingDocument


def make_request(with_documents: bool = True) -> PriorAuthRequest:
    return PriorAuthRequest(
        request_id="PA-2026-00042",
        patient_id="PT-88213",
        provider_npi="1234567893",
        payer_id="PAYER-BCBS-CA",
        procedure_code="70551",
        diagnosis_code="G43.909",
        supporting_documents=(
            [SupportingDocument(doc_type="clinical_notes", url="https://x/1.pdf")]
            if with_documents
            else []
        ),
        submitted_at="2026-08-10T14:32:00Z",
    )


class CountingTool:
    """Wraps a tool function, counting calls and letting a test control
    exactly how many times it fails before succeeding (or fails forever)."""

    def __init__(self, real_fn, fail_times: int = 0, fail_forever: bool = False):
        self.real_fn = real_fn
        self.fail_times = fail_times
        self.fail_forever = fail_forever
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        if self.fail_forever or self.call_count <= self.fail_times:
            raise TimeoutError("simulated failure")
        return self.real_fn(*args, fail_mode=None)


def fake_eligibility(patient_id, payer_id, fail_mode=None):
    return {"eligible": True, "plan_type": "PPO", "payer_id": payer_id}


def fake_imaging(patient_id, procedure_code, fail_mode=None):
    return {"has_prior_imaging": False, "most_recent_date": None}


def fake_notes(patient_id, fail_mode=None):
    return {"notes_text": "some notes", "author_npi": "1234567893"}


def test_happy_path_fills_in_eligibility_and_imaging():
    request = make_request(with_documents=True)
    tools = AgentTools(
        fetch_eligibility=fake_eligibility,
        fetch_prior_imaging=fake_imaging,
        fetch_clinical_notes=fake_notes,
    )
    result = run_validation_loop(request, tools)
    assert isinstance(result, ValidationResult)
    assert result.eligibility is not None
    assert result.prior_imaging is not None
    assert result.unresolved == []


def test_missing_supporting_documents_triggers_clinical_notes_fetch():
    request = make_request(with_documents=False)
    notes_tool = CountingTool(fake_notes)
    tools = AgentTools(
        fetch_eligibility=fake_eligibility,
        fetch_prior_imaging=fake_imaging,
        fetch_clinical_notes=lambda patient_id, fail_mode=None: notes_tool(
            patient_id
        ),
    )
    result = run_validation_loop(request, tools)
    assert notes_tool.call_count >= 1
    assert result.clinical_notes is not None


def test_present_supporting_documents_skips_clinical_notes_fetch():
    request = make_request(with_documents=True)
    notes_tool = CountingTool(fake_notes)
    tools = AgentTools(
        fetch_eligibility=fake_eligibility,
        fetch_prior_imaging=fake_imaging,
        fetch_clinical_notes=lambda patient_id, fail_mode=None: notes_tool(
            patient_id
        ),
    )
    run_validation_loop(request, tools)
    assert notes_tool.call_count == 0


def test_transient_tool_failure_recovers_via_retry():
    request = make_request(with_documents=True)
    flaky_eligibility = CountingTool(fake_eligibility, fail_times=2)
    tools = AgentTools(
        fetch_eligibility=lambda patient_id, payer_id, fail_mode=None: flaky_eligibility(
            patient_id, payer_id
        ),
        fetch_prior_imaging=fake_imaging,
        fetch_clinical_notes=fake_notes,
    )
    result = run_validation_loop(request, tools)
    assert flaky_eligibility.call_count == 3  # failed twice, succeeded on the 3rd
    assert result.eligibility is not None
    assert "eligibility" not in result.unresolved


def test_permanently_failing_tool_is_recorded_not_raised():
    request = make_request(with_documents=True)
    dead_eligibility = CountingTool(fake_eligibility, fail_forever=True)
    tools = AgentTools(
        fetch_eligibility=lambda patient_id, payer_id, fail_mode=None: dead_eligibility(
            patient_id, payer_id
        ),
        fetch_prior_imaging=fake_imaging,
        fetch_clinical_notes=fake_notes,
    )
    # Must not raise -- a permanently failing dependency is recorded, not fatal.
    result = run_validation_loop(request, tools)
    assert result.eligibility is None
    assert "eligibility" in result.unresolved
    # Other tool calls still completed despite eligibility failing entirely.
    assert result.prior_imaging is not None
