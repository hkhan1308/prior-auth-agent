"""
Phase 1 -- Reliability layer: circuit breaker.

Contract:
    CircuitBreaker(failure_threshold=5, reset_timeout=30.0)

    States: CLOSED, OPEN, HALF_OPEN

    .call(func, *args, **kwargs):
        - CLOSED: call func normally. On failure, increment a failure
          counter. If the counter reaches `failure_threshold`, transition
          to OPEN and record the time it opened.
        - OPEN: reject calls immediately by raising CircuitBreakerOpenError,
          WITHOUT calling func, until `reset_timeout` seconds have passed
          since opening. After that, transition to HALF_OPEN.
        - HALF_OPEN: allow exactly one call through as a probe. On success,
          transition to CLOSED and reset the failure counter. On failure,
          transition back to OPEN and reset the timer.

Not implemented. See tests/test_reliability.py.
"""
from enum import Enum
from typing import Callable
import time

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.state = CircuitState.CLOSED
        # TODO: whatever internal bookkeeping you need
        # (failure count, time the circuit opened, etc.)

        self.failure_count = 0
        self.opened_at: float | None = None 



    def call(self, func: Callable, *args, **kwargs):
        if self.state == CircuitState.CLOSED:
            try:
                result = func(*args,**kwargs)
                self.failure_count = 0
                return result 
            except Exception:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self.opened_at = time.time()
                    self.state = CircuitState.OPEN
                # Outside the if: crossing the threshold decides whether the
                # circuit opens, not whether the caller sees their error.
                raise

        if self.state == CircuitState.OPEN:
            if time.time() - self.opened_at < self.reset_timeout:
                # Still cooling down: reject without ever calling func.
                raise CircuitBreakerOpenError(
                    f"circuit open, retry in "
                    f"{self.reset_timeout - (time.time() - self.opened_at):.2f}s"
                )
            # Cooldown elapsed. Promote and fall through so the probe below
            # runs on this same call rather than costing the caller a reject.
            self.state = CircuitState.HALF_OPEN

        if self.state == CircuitState.HALF_OPEN:
            try:
                result = func(*args, **kwargs)
            except Exception:
                # Probe failed: reopen and restart the cooldown from now.
                self.state = CircuitState.OPEN
                self.opened_at = time.time()
                raise
            else:
                # Probe succeeded: close, and clear the count so the next
                # failure starts a fresh streak toward the threshold.
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                return result
