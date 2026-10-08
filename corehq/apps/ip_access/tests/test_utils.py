import pytest

from django.test import RequestFactory

from ..utils import ORIGIN_IP_HEADER, get_origin_ip


@pytest.mark.parametrize("header_value, expected", [
    ('203.0.113.7', '203.0.113.7'),
    ('2001:db8::1', '2001:db8::1'),
    # formplayer forwards X-Forwarded-For verbatim, which may list proxies
    ('203.0.113.7, 10.0.0.1', '203.0.113.7'),
    (' 203.0.113.7 ', '203.0.113.7'),
    ('', None),
    ('not-an-ip', None),
    ('999.0.0.1', None),
    ('203.0.113.7; DROP TABLE', None),
])
def test_get_origin_ip(header_value, expected):
    request = RequestFactory().post('/', **{ORIGIN_IP_HEADER: header_value})
    assert get_origin_ip(request) == expected


def test_get_origin_ip_without_header():
    request = RequestFactory().post('/')
    assert get_origin_ip(request) is None
