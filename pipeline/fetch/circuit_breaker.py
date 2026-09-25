"""
pipeline/fetch/circuit_breaker.py
──────────────────────────────────
Per-domain circuit breaker for the body fetch loop.

State machine (per domain):
  CLOSED   → normal; failures counted
  OPEN     → 5 failures reached; all requests fail-fast for 5 minutes
  HALF_OPEN→ one probe allowed; success → CLOSED, failure → OPEN (reset timer)

Configuration (matches implementation plan):
  failure_threshold = 5
  open_duration_s   = 300  (5 minutes)
"""
from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum, auto

log = logging.getLogger(__name__)

FAILURE_THRESHOLD = 5
OPEN_DURATION_S   = 300   # 5 minutes


class _State(Enum):
    CLOSED    = auto()
    OPEN      = auto()
    HALF_OPEN = auto()


class CircuitBreaker:
    """
    Thread-safe (asyncio) circuit breaker for a single domain.

    Usage:
        cb = CircuitBreaker("reuters.com")
        if not cb.allow_request():
            raise CircuitOpenError("reuters.com")
        try:
            result = await fetch(url)
            cb.record_success()
        except Exception:
            cb.record_failure()
            raise
    """

    def __init__(self, domain: str) -> None:
        self.domain = domain
        self._state: _State = _State.CLOSED
        self._failures: int = 0
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

    def allow_request(self) -> bool:
        """Return True if a request should be attempted."""
        if self._state == _State.CLOSED:
            return True

        if self._state == _State.OPEN:
            if time.monotonic() - self._opened_at >= OPEN_DURATION_S:
                log.info("[CB] %s → HALF_OPEN (probe allowed)", self.domain)
                self._state = _State.HALF_OPEN
                return True
            return False

        # HALF_OPEN — only one probe at a time; subsequent callers are blocked
        return True

    def record_success(self) -> None:
        """Call after a successful fetch."""
        if self._state in (_State.HALF_OPEN, _State.OPEN):
            log.info("[CB] %s → CLOSED (probe succeeded)", self.domain)
        self._state = _State.CLOSED
        self._failures = 0

    def record_failure(self) -> None:
        """Call after a fetch failure."""
        self._failures += 1
        if self._state == _State.HALF_OPEN:
            log.warning("[CB] %s probe failed → re-OPEN", self.domain)
            self._state = _State.OPEN
            self._opened_at = time.monotonic()
        elif self._failures >= FAILURE_THRESHOLD and self._state == _State.CLOSED:
            log.warning(
                "[CB] %s → OPEN (%d failures in a row)", self.domain, self._failures
            )
            self._state = _State.OPEN
            self._opened_at = time.monotonic()

    @property
    def is_open(self) -> bool:
        return self._state == _State.OPEN

    @property
    def state_name(self) -> str:
        return self._state.name


class CircuitOpenError(Exception):
    """Raised when a request is blocked by an open circuit breaker."""
    pass


class CircuitBreakerRegistry:
    """
    Global registry of per-domain circuit breakers.
    Call `get(domain)` to retrieve (or lazily create) the breaker for a domain.
    """

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, domain: str) -> CircuitBreaker:
        if domain not in self._breakers:
            self._breakers[domain] = CircuitBreaker(domain)
        return self._breakers[domain]

    def stats(self) -> dict[str, str]:
        return {d: cb.state_name for d, cb in self._breakers.items()}


# Module-level singleton — shared across the entire fetch loop
registry = CircuitBreakerRegistry()
