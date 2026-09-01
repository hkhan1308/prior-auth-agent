"""
Phase 1 tests. These define the contract for the reliability layer.
Implement src/reliability/retry.py and src/reliability/circuit_breaker.py
until every test here passes. Don't edit these tests to make them pass --
if you think a test is wrong, that's worth raising in review, not silently
changing.
"""
import time
import pytest

from src.reliability.retry import retry_with_backoff
from src.reliability.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class FlakyFunction:
    """Fails `fail_times` times, then succeeds."""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ConnectionError(f"attempt {self.calls} failed")
        return "success"


def test_retry_succeeds_after_transient_failures():
    flaky = FlakyFunction(fail_times=2)
    decorated = retry_with_backoff(max_attempts=3, base_delay=0.01)(flaky)
    result = decorated()
    assert result == "success"
    assert flaky.calls == 3


def test_retry_raises_after_exhausting_attempts():
    flaky = FlakyFunction(fail_times=5)
    decorated = retry_with_backoff(max_attempts=3, base_delay=0.01)(flaky)
    with pytest.raises(ConnectionError):
        decorated()
    assert flaky.calls == 3  # stops at max_attempts, doesn't keep going forever


def test_retry_does_not_retry_unlisted_exceptions():
    def always_type_error():
        raise TypeError("not retryable")

    decorated = retry_with_backoff(
        max_attempts=3, base_delay=0.01, exceptions=(ConnectionError,)
    )(always_type_error)

    with pytest.raises(TypeError):
        decorated()


def test_retry_backoff_grows_between_attempts(monkeypatch):
    delays = []

    def fake_sleep(seconds):
        delays.append(seconds)

    import src.reliability.retry as retry_module

    monkeypatch.setattr(retry_module.time, "sleep", fake_sleep)

    flaky = FlakyFunction(fail_times=2)
    decorated = retry_with_backoff(max_attempts=3, base_delay=0.1)(flaky)
    decorated()

    assert len(delays) == 2  # slept between attempt 1->2 and 2->3
    assert delays[1] > delays[0]  # backoff grows, not constant


def test_circuit_opens_after_threshold_failures():
    breaker = CircuitBreaker(failure_threshold=3, reset_timeout=100)

    def always_fails():
        raise ConnectionError("down")

    for _ in range(3):
        with pytest.raises(ConnectionError):
            breaker.call(always_fails)

    # 4th call should be rejected by the breaker itself, not hit always_fails
    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(always_fails)


def test_circuit_half_opens_after_timeout_and_recovers():
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=0.05)

    def always_fails():
        raise ConnectionError("down")

    for _ in range(2):
        with pytest.raises(ConnectionError):
            breaker.call(always_fails)

    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(always_fails)

    time.sleep(0.1)  # past reset_timeout -> should allow a probe call

    def now_succeeds():
        return "ok"

    result = breaker.call(now_succeeds)
    assert result == "ok"

    # breaker should be CLOSED again after the successful probe --
    # a single subsequent failure should not immediately reopen it
    with pytest.raises(ConnectionError):
        breaker.call(always_fails)
    result2 = breaker.call(now_succeeds)
    assert result2 == "ok"
