import logging
from unittest.mock import patch

import requests
from nose.tools import assert_equal

from corehq.motech.auth import BasicAuthManager
from corehq.motech.const import REQUEST_TIMEOUT
from corehq.motech.models import RequestLog
from corehq.motech.requests import simple_post

TEST_DOMAIN = 'pet-shop'
TEST_API_URL = 'https://www.example.com/api/'
TEST_API_USERNAME = 'michael'
TEST_API_PASSWORD = 'Norwegi4n_Blue'
TEST_PAYLOAD_ID = 'abc123'


def test_simple_post():
    with patch.object(requests.Session, 'request') as request_mock, \
            patch.object(RequestLog, 'log') as log_mock:
        auth_manager = BasicAuthManager(TEST_API_USERNAME, TEST_API_PASSWORD)
        simple_post(
            domain=TEST_DOMAIN,
            url=TEST_API_URL,
            data='<payload id="abc123"><parrot status="déad" /></payload>',
            headers={'Content-Type': 'text/xml+parrot'},
            auth_manager=auth_manager,
            verify=True,
            payload_id=TEST_PAYLOAD_ID,
        )

        request_mock.assert_called_with(
            'POST',
            TEST_API_URL,
            data=b'<payload id="abc123"><parrot status="d\xc3\xa9ad" /></payload>',
            headers={
                'Content-Type': 'text/xml+parrot',
                'content-length': '56',
            },
            json=None,
            timeout=REQUEST_TIMEOUT,
        )
        ((__, (level, log_entry), ___),) = log_mock.mock_calls
        assert_equal(level, logging.INFO)
        assert_equal(log_entry.payload_id, TEST_PAYLOAD_ID)
