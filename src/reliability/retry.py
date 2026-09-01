"""
Phase 1 -- Reliability layer: retry with exponential backoff.

Contract:
    retry_with_backoff(max_attempts=3, base_delay=0.5, exceptions=(Exception,))
    is a decorator. When the wrapped function raises one of `exceptions`:
        - retry up to `max_attempts` times total (including the first call)
        - delay between attempts grows exponentially: base_delay * 2 ** (attempt - 1)
        - add jitter to the delay (don't sleep the exact same amount every time)
        - if all attempts are exhausted, re-raise the last exception
    If the wrapped function raises an exception NOT listed in `exceptions`,
    do not retry -- let it propagate immediately on the first attempt.

Jitter strategy
---------------
The nominal backoff for attempt `n` is `base_delay * 2 ** (n - 1)`, and the
actual sleep is that value scaled by a random factor in
`[1 - JITTER_RATIO, 1 + JITTER_RATIO]`.

JITTER_RATIO is held below 1/3 on purpose: it is the largest spread for
which consecutive delay *windows* cannot overlap, since
`(1 + j) * b < (1 - j) * 2b` exactly when `j < 1/3`. That keeps backoff
strictly monotonic on every run instead of merely on average, which is what
the test asserts (`delays[1] > delays[0]`) and what makes the behaviour
debuggable in a trace.

Full jitter (`uniform(0, backoff)`, the AWS-blog variant) decorrelates
retrying clients more aggressively and is the better choice under real
thundering-herd load, but it can legitimately produce a shorter second
delay than first. Worth revisiting if this ever fronts a service with many
concurrent callers -- see the note in the review summary.

`max_delay` caps the exponential so a high `max_attempts` can't produce an
unbounded sleep. Once the cap binds, successive delays stop growing.
"""
import logging
import random
import time
from functools import wraps
from typing import Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)

#: Fractional spread of the random jitter around the nominal backoff.
#: Must stay < 1/3 to keep consecutive delay windows non-overlapping.
JITTER_RATIO = 0.25

#: Default ceiling on a single sleep, in seconds.
DEFAULT_MAX_DELAY = 30.0

# Dedicated RNG so jitter never perturbs the global `random` stream, which a
# caller may have seeded for reproducibility elsewhere in the pipeline.
_rng = random.Random()


def _compute_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Jittered backoff, in seconds, to sleep *after* the given attempt.

    `attempt` is 1-based, so the first retry sleeps roughly `base_delay`.
    """
    backoff = min(base_delay * (2 ** (attempt - 1)), max_delay)
    return backoff * _rng.uniform(1.0 - JITTER_RATIO, 1.0 + JITTER_RATIO)


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 0.5,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    max_delay: float = DEFAULT_MAX_DELAY,
    on_retry: Optional[Callable[[BaseException, int, float], None]] = None,
) -> Callable:
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
    if base_delay < 0:
        raise ValueError(f"base_delay must be >= 0, got {base_delay}")
    if max_delay < 0:
        raise ValueError(f"max_delay must be >= 0, got {max_delay}")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                
                    if attempt >= max_attempts:
                        logger.warning(
                            "%s failed after %d/%d attempts, giving up: %r",
                            getattr(func, "__name__", repr(func)),
                            attempt,
                            max_attempts,
                            exc,
                        )
                        raise

                    delay = _compute_delay(attempt, base_delay, max_delay)
                    logger.info(
                        "%s failed on attempt %d/%d (%r), retrying in %.3fs",
                        getattr(func, "__name__", repr(func)),
                        attempt,
                        max_attempts,
                        exc,
                        delay,
                    )
                    if on_retry is not None:
                        on_retry(exc, attempt, delay)
                    time.sleep(delay)

            # Unreachable: the loop either returns or raises. Guards against a
            # silent `None` if the bounds above are ever edited carelessly.
            raise AssertionError("retry loop exited without returning or raising")

        # Expose config for tests, tracing, and introspection at call sites.
        wrapper.retry_config = {
            "max_attempts": max_attempts,
            "base_delay": base_delay,
            "exceptions": exceptions,
            "max_delay": max_delay,
        }
        return wrapper

    return decorator
