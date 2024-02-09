from testil import eq, assert_raises

from dimagi.utils.web import get_ip, json_request


def test_get_ip():
    # localhost default
    yield _test_get_ip, {}, '127.0.0.1'
    # garbage default
    yield _test_get_ip, {'REMOTE_ADDR': 'garbage'}, '10.0.0.1'
    # Use x-forwarded-for
    yield _test_get_ip, {'HTTP_X_FORWARDED_FOR': '54.13.132.27'}, '54.13.132.27'
    # Use remote address
    yield _test_get_ip, {'REMOTE_ADDR': '44.44.44.44'}, '44.44.44.44'
    # Use x-forwarded-for over remote address
    yield _test_get_ip, {'HTTP_X_FORWARDED_FOR': '54.13.132.27', 'REMOTE_ADDR': '44.44.44.44'}, '54.13.132.27'
    # Use x-forwarded-for first IP address if many
    yield _test_get_ip, {'HTTP_X_FORWARDED_FOR': '54.13.132.27, 10.200.40.12'}, '54.13.132.27'
    # Use x-forwarded-for first IP address if many (even if no space)
    yield _test_get_ip, {'HTTP_X_FORWARDED_FOR': '54.13.132.27,10.200.40.12'}, '54.13.132.27'


def _test_get_ip(request_meta, expected_value):
    class FakeRequest:
        def __init__(self):
            self.META = request_meta

    eq(get_ip(FakeRequest()), expected_value)


def test_json_request():
    # empty
    yield _test_json_request, {}, {}, {}
    # quoted string
    yield _test_json_request, {'hello': '"world"'}, {}, {'hello': 'world'}
    # string of an integer
    yield _test_json_request, {'hello': '123'}, {}, {'hello': 123}
    # string of an object
    yield (
        _test_json_request,
        {'hello': '{"foo": "bar"}'},
        {},
        {'hello': {'foo': 'bar'}},
    )
    # boolean
    yield (
        _test_json_request,
        {'hello': 'true'},
        {},
        {'hello': True},
    )
    # booleans as strings
    yield (
        _test_json_request,
        {'hello': 'true'},
        {'booleans_as_strings': True},
        {'hello': 'true'},
    )
    # key is not a string
    yield _test_json_request, {123: '"world"'}, {}, {'123': 'world'}
    # lenient
    yield (
        _test_json_request,
        {'hello': 'not JSON'},
        {},  # {'lenient': True}
        {'hello': 'not JSON'},
    )


def _test_json_request(params, kwargs, expected_result):
    eq(json_request(params, **kwargs), expected_result)


def test_not_lenient_json_request():
    with assert_raises(ValueError):
        json_request({'hello': 'not JSON'}, lenient=False)
