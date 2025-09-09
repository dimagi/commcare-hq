from contextlib import contextmanager
from unittest.mock import patch

import pytest
from testil import assert_raises, eq

from corehq.util.test_utils import timelimit
from .. import retry as mod


class Error(Exception):
    pass


class OtherError(Exception):
    pass


@pytest.mark.parametrize("n, error", [
    (0, Error),
    (1, Error),
    (2, Error),
    (3, Error),
    (4, Error),
    (5, Error),
    (1, OtherError),
])
@timelimit
def test_retry_on(n, error):
    retry = mod.retry_on(Error, OtherError)

    func, calls = make_retry_function(retry, n, error)
    with mock_retry_sleep() as sleeps:
        eq(func(n), n * 2)
    eq(sleeps, ([0.1] + [2 ** i for i in range(n - 1)]) if n else [])
    eq(len(calls), n + 1)


@timelimit
def test_retry_on_too_many_retries():
    retry = mod.retry_on(Error, OtherError)
    func, calls = make_retry_function(retry, 6, Error)
    with mock_retry_sleep() as sleeps, assert_raises(Error):
        func(1)
    eq(sleeps, [0.1, 1, 2, 4, 8])
    eq(len(calls), 6)


@timelimit
def test_retry_on_non_retry_error():
    @mod.retry_on(Error)
    def func():
        calls.append(1)
        raise OtherError()

    calls = []
    with assert_raises(OtherError):
        func()
    eq(calls, [1])


@timelimit
def test_retry_with_delays():
    retry = mod.retry_on(Error, delays=[2 ** x for x in range(5)])
    func, calls = make_retry_function(retry, 6, Error)
    with mock_retry_sleep() as sleeps, assert_raises(Error):
        func(1)
    eq(sleeps, [1, 2, 4, 8, 16])
    eq(len(calls), 6)


def make_retry_function(decorator, n_errors, error):
    @decorator
    def maybe_error(arg):
        nonlocal n_errors
        calls.append(1)
        n_errors -= 1
        if n_errors < 0:
            return arg * 2
        raise error
    calls = []
    return maybe_error, calls


@contextmanager
def mock_retry_sleep():
    def fake_sleep(delay):
        sleeps.append(delay)
        print(f"fake sleep for {delay}s")
    sleeps = []
    with patch.object(mod, "sleep", fake_sleep):
        yield sleeps
