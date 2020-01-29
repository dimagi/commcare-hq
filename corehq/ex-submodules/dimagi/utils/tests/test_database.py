from mock import patch
from testil import Config, assert_raises, eq

from requests.exceptions import RequestException

from corehq.util.test_utils import timelimit
from ..couch import database as mod


def test_retry_on_couch_error():
    @timelimit
    def test(n, error=None):
        fake_sleep, sleeps = make_sleeper()
        func, calls = make_retry_function(n, error)
        with patch.object(mod, "sleep", fake_sleep):
            eq(func(n), n * 2)
        eq(sleeps, ([0.1] + [2 ** i for i in range(n - 1)]) if n else [])
        eq(len(calls), n + 1)

    yield test, 0
    yield test, 1
    yield test, 2
    yield test, 3
    yield test, 4
    yield test, 5

    yield test, 1, mod.BulkFetchException


@timelimit
def test_retry_on_couch_error_too_many_retries():
    fake_sleep, sleeps = make_sleeper()
    func, calls = make_retry_function(6)
    with patch.object(mod, "sleep", fake_sleep):
        with assert_raises(RequestException):
            func(1)
    eq(sleeps, [0.1, 1, 2, 4, 8])
    eq(len(calls), 6)


@timelimit
def test_retry_on_couch_error_non_couch_error():
    @mod.retry_on_couch_error
    def func():
        calls.append(1)
        raise RequestException()

    calls = []
    with assert_raises(RequestException):
        func()
    eq(calls, [1])


def make_retry_function(n_errors, error=None):
    @mod.retry_on_couch_error
    def maybe_error(arg):
        nonlocal n_errors
        calls.append(1)
        n_errors -= 1
        if n_errors < 0:
            return arg * 2
        raise error
    if error is None:
        couch_url = mod._get_couch_base_urls()[0] + "/some/path"
        error = mod.RequestException(request=Config(url=couch_url))
    calls = []
    return maybe_error, calls


def make_sleeper():
    def fake_sleep(delay):
        sleeps.append(delay)
        print(f"fake sleep for {delay}s")
    sleeps = []
    return fake_sleep, sleeps
