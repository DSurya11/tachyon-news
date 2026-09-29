import time

import httpx

from pipeline.fetch import circuit_breaker
from pipeline.fetch.body_fetcher import _is_retryable, domain_of, is_skipped_domain
from pipeline.fetch.circuit_breaker import CircuitBreaker


def test_domain_of_strips_only_the_www_prefix():
    assert domain_of("https://www.wsj.com/articles/x") == "wsj.com"
    assert domain_of("https://wsj.com/x") == "wsj.com"  # old lstrip("www.") produced "sj.com"
    assert domain_of("https://web.archive.org/x") == "web.archive.org"


def test_skip_domains_match_subdomains():
    skip = frozenset({"wsj.com"})
    assert is_skipped_domain("wsj.com", skip)
    assert is_skipped_domain("markets.wsj.com", skip)
    assert not is_skipped_domain("notwsj.com", skip)


def test_only_transient_errors_are_retried():
    def status_error(code):
        req = httpx.Request("GET", "https://x")
        return httpx.HTTPStatusError("e", request=req, response=httpx.Response(code, request=req))

    assert _is_retryable(status_error(503))
    assert _is_retryable(status_error(429))
    assert not _is_retryable(status_error(403))
    assert not _is_retryable(status_error(404))
    assert _is_retryable(httpx.ConnectError("boom"))


def test_circuit_breaker_opens_and_allows_single_probe(monkeypatch):
    cb = CircuitBreaker("example.com")
    for _ in range(circuit_breaker.FAILURE_THRESHOLD):
        assert cb.allow_request()
        cb.record_failure()
    assert cb.is_open and not cb.allow_request()

    now = time.monotonic()
    monkeypatch.setattr(circuit_breaker.time, "monotonic", lambda: now + circuit_breaker.OPEN_DURATION_S + 1)
    assert cb.allow_request()          # the probe
    assert not cb.allow_request()      # everyone else waits for it
    cb.record_success()
    assert cb.state_name == "CLOSED" and cb.allow_request()
