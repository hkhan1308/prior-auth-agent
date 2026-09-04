"""
Phase 3 -- Agent loop.

Contract:
    run_validation_loop(request: PriorAuthRequest, tools: AgentTools) -> ValidationResult

    Given a validated request, figure out what additional information is
    needed to support a decision, and go get it:

      - Every request needs an eligibility check:
        tools.fetch_eligibility(request.patient_id, request.payer_id)
      - Every request needs prior imaging history:
        tools.fetch_prior_imaging(request.patient_id, request.procedure_code)
      - If request.supporting_documents is empty, clinical notes are
        missing -- fetch them: tools.fetch_clinical_notes(request.patient_id)

    Every tool call MUST go through the reliability layer.
"""
import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from src.ingestion.models import PriorAuthRequest
from src.reliability.circuit_breaker import CircuitBreakerOpenError
from src.reliability.retry import retry_with_backoff

logger = logging.getLogger(__name__)

#: Total attempts per tool call, including the first.
TOOL_MAX_ATTEMPTS = 3

#: Base backoff between tool retries. Short on purpose -- these are
#: interactive-path calls, not a batch job.
TOOL_BASE_DELAY = 0.05


@dataclass
class AgentTools:
    """Bundles the tool functions so tests can substitute controllable fakes."""

    fetch_eligibility: Callable
    fetch_prior_imaging: Callable
    fetch_clinical_notes: Callable


@dataclass
class ValidationResult:
    eligibility: Optional[dict] = None
    prior_imaging: Optional[dict] = None
    clinical_notes: Optional[dict] = None
    unresolved: List[str] = field(default_factory=list)



def _call_tool_safely(fn, *args, name: str) -> Optional[dict]:
    """Calls fn through the reliability layer. Returns the result on
    success, or None on failure (caller is responsible for recording
    `name` in unresolved when this returns None)."""
    # An open circuit is a decision to stop calling, not a transient
    # fault -- retrying it would defeat the breaker, so it is excluded
    # from the retryable set and falls straight through to the handler.
    retrying = retry_with_backoff(
        max_attempts=TOOL_MAX_ATTEMPTS,
        base_delay=TOOL_BASE_DELAY,
        exceptions=(TimeoutError, ConnectionError, OSError),
    )(fn)

    try:
        return retrying(*args)
    except CircuitBreakerOpenError as exc:
        logger.warning("%s unavailable, circuit open: %r", name, exc)
        return None
    except Exception as exc:
        # Retries exhausted, or a failure the retry layer refused to
        # retry. Either way the caller gets None and keeps going -- one
        # dead dependency must not sink the whole request.
        logger.warning("%s unresolved after %d attempts: %r", name, TOOL_MAX_ATTEMPTS, exc)
        return None




def run_validation_loop(request: PriorAuthRequest, tools: AgentTools) -> ValidationResult:
    eligibility = _call_tool_safely(tools.fetch_eligibility, request.patient_id, request.payer_id, name="eligibility")
    prior_imaging = _call_tool_safely(tools.fetch_prior_imaging, request.patient_id, request.procedure_code, name="prior_imaging")
    needs_notes = not request.supporting_documents
    if needs_notes:
        clinical_notes = _call_tool_safely(tools.fetch_clinical_notes, request.patient_id, name="clinical_notes")
    else:
        clinical_notes = None

    # A None result means the reliability layer gave up on that call. Notes
    # are only unresolved if we actually needed them -- skipping the fetch
    # because documents were attached is a success, not a failure.
    unresolved = []
    if eligibility is None:
        unresolved.append("eligibility")
    if prior_imaging is None:
        unresolved.append("prior_imaging")
    if needs_notes and clinical_notes is None:
        unresolved.append("clinical_notes")

    return ValidationResult(
        eligibility=eligibility,
        prior_imaging=prior_imaging,
        clinical_notes=clinical_notes,
        unresolved=unresolved,
    )
