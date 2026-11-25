import pytest
import requests

from corehq.messaging.smsbackends.connectid.backend import (
    MAX_ERROR_DETAIL_LENGTH,
    get_error_detail,
)


def _response(body):
    response = requests.Response()
    response.status_code = 400
    response._content = body.encode()
    return response


@pytest.mark.parametrize('body, expected', [
    ('{"errors": "CHANNEL_DOES_NOT_EXIST"}', 'CHANNEL_DOES_NOT_EXIST'),
    # DRF's own errors, e.g. bad client credentials
    ('{"detail": "Invalid username/password."}', '{"detail": "Invalid username/password."}'),
    ('["not", "an", "object"]', '["not", "an", "object"]'),
    ('<h1>Server Error (500)</h1>', '<h1>Server Error (500)</h1>'),
    ('', ''),
])
def test_get_error_detail(body, expected):
    assert get_error_detail(_response(body)) == expected


def test_get_error_detail_truncates_long_bodies():
    body = '<html>' + 'x' * 1000 + '</html>'

    assert get_error_detail(_response(body)) == body[:MAX_ERROR_DETAIL_LENGTH]
