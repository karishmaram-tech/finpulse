"""Unit tests for finpulse.utils.resilience.retry_with_backoff."""

import pytest

from finpulse.utils.resilience import retry_with_backoff


def test_succeeds_on_first_try():
    calls = []

    @retry_with_backoff(max_retries=3, base_delay=0.01)
    def always_works():
        calls.append(1)
        return "ok"

    assert always_works() == "ok"
    assert len(calls) == 1


def test_retries_then_succeeds():
    calls = []

    @retry_with_backoff(max_retries=3, base_delay=0.01)
    def fails_twice_then_works():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("transient")
        return "ok"

    assert fails_twice_then_works() == "ok"
    assert len(calls) == 3


def test_raises_after_max_retries_exhausted():
    calls = []

    @retry_with_backoff(max_retries=2, base_delay=0.01)
    def always_fails():
        calls.append(1)
        raise ValueError("permanent failure")

    with pytest.raises(ValueError, match="permanent failure"):
        always_fails()
    assert len(calls) == 2
