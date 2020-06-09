from testil import eq

from dimagi.utils.web import get_ip


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
