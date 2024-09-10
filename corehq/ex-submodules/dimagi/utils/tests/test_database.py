import pytest
from testil import Config, assert_raises, eq

from requests.exceptions import RequestException

from corehq.util.test_utils import timelimit
from .test_retry import make_retry_function, mock_retry_sleep
from ..couch import database as mod


@pytest.mark.parametrize("n, error", [
    (0, None),
    (1, None),
    (2, None),
    (3, None),
    (4, None),
    (5, None),
    (1, mod.BulkFetchException),
])
@timelimit
def test_retry_on_couch_error(n, error):
    func, calls = make_couch_retry_function(n, error)
    with mock_retry_sleep() as sleeps:
        eq(func(n), n * 2)
    eq(sleeps, ([0.1] + [2 ** i for i in range(n - 1)]) if n else [])
    eq(len(calls), n + 1)


@timelimit
def test_retry_on_couch_error_too_many_retries():
    func, calls = make_couch_retry_function(6)
    with mock_retry_sleep() as sleeps, assert_raises(RequestException):
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


def make_couch_retry_function(n_errors, error=None):
    if error is None:
        couch_url = mod._get_couch_base_urls()[0] + "/some/path"
        error = mod.RequestException(request=Config(url=couch_url))
    return make_retry_function(mod.retry_on_couch_error, n_errors, error)
