import pytest
import time
from app.utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState


def test_circuit_breaker_normal_operation():
    cb = CircuitBreaker(name="test_cb", failure_threshold=2, recovery_timeout=0.5)

    def dummy():
        return "ok"

    res = cb.execute(dummy)
    assert res == "ok"
    assert cb.state == CircuitState.CLOSED


func_failures = 0


def test_circuit_breaker_tripping():
    cb = CircuitBreaker(name="test_trip", failure_threshold=2, recovery_timeout=0.2)

    def failing_func():
        raise ValueError("transient error")

    # Failure 1
    with pytest.raises(ValueError):
        cb.execute(failing_func)
    assert cb.state == CircuitState.CLOSED

    # Failure 2 -> trips circuit to OPEN
    with pytest.raises(ValueError):
        cb.execute(failing_func)
    assert cb.state == CircuitState.OPEN

    # Subsequent call fails immediately with CircuitBreakerOpenError without executing failing_func
    with pytest.raises(CircuitBreakerOpenError):
        cb.execute(failing_func)

    # Wait for recovery timeout
    time.sleep(0.25)
    assert cb.state == CircuitState.HALF_OPEN

    # Successful call in HALF_OPEN restores circuit to CLOSED
    def success_func():
        return "restored"

    res = cb.execute(success_func)
    assert res == "restored"
    assert cb.state == CircuitState.CLOSED
