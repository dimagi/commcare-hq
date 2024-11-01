import pytest
from testil import eq, assert_raises

from dimagi.utils.web import get_ip, json_request


@pytest.mark.parametrize("request_meta, expected_value", [
    # localhost default
    ({}, '127.0.0.1'),
    # garbage default
    ({'REMOTE_ADDR': 'garbage'}, '10.0.0.1'),
    # Use x-forwarded-for
    ({'HTTP_X_FORWARDED_FOR': '54.13.132.27'}, '54.13.132.27'),
    # Use remote address
    ({'REMOTE_ADDR': '44.44.44.44'}, '44.44.44.44'),
    # Use x-forwarded-for over remote address
    ({'HTTP_X_FORWARDED_FOR': '54.13.132.27', 'REMOTE_ADDR': '44.44.44.44'}, '54.13.132.27'),
    # Use x-forwarded-for first IP address if many
    ({'HTTP_X_FORWARDED_FOR': '54.13.132.27, 10.200.40.12'}, '54.13.132.27'),
    # Use x-forwarded-for first IP address if many (even if no space)
    ({'HTTP_X_FORWARDED_FOR': '54.13.132.27,10.200.40.12'}, '54.13.132.27'),
])
def test_get_ip(request_meta, expected_value):
    class FakeRequest:
        def __init__(self):
            self.META = request_meta

    eq(get_ip(FakeRequest()), expected_value)


@pytest.mark.parametrize("params, kwargs, expected_result", [
    # empty
    ({}, {}, {}),
    # quoted string
    ({'hello': '"world"'}, {}, {'hello': 'world'}),
    # string of an integer
    ({'hello': '123'}, {}, {'hello': 123}),
    # string of an object
    ({'hello': '{"foo": "bar"}'}, {}, {'hello': {'foo': 'bar'}}),
    # boolean
    ({'hello': 'true'}, {}, {'hello': True}),
    # booleans as strings
    ({'hello': 'true'}, {'booleans_as_strings': True}, {'hello': 'true'}),
    # key is not a string
    ({123: '"world"'}, {}, {'123': 'world'}),
    # lenient
    ({'hello': 'not JSON'}, {}, {'hello': 'not JSON'}),  # {} -> {'lenient': True}
])
def test_json_request(params, kwargs, expected_result):
    eq(json_request(params, **kwargs), expected_result)


def test_not_lenient_json_request():
    with assert_raises(ValueError):
        json_request({'hello': 'not JSON'}, lenient=False)
