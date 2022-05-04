import logging
from unittest.mock import patch

import requests
from nose.tools import assert_equal

from corehq.motech.auth import BasicAuthManager
from corehq.motech.const import REQUEST_TIMEOUT
from corehq.motech.models import RequestLog
from corehq.motech.requests import Requests, simple_post, simple_request

TEST_DOMAIN = 'pet-shop'
TEST_API_URL = 'https://www.example.com/api/'
TEST_API_USERNAME = 'michael'
TEST_API_PASSWORD = 'Norwegi4n_Blue'
TEST_PAYLOAD_ID = 'abc123'


class Response:
    status_code = 200
    content = b'OK'
    headers = {
        'Content-Length': '2',
        'Content-Type': 'text/plain',
    }

    @property
    def text(self):
        return self.content.decode('utf-8')


def test_simple_request_with_PUT():
    with patch.object(requests.Session, 'request') as request_mock, \
            patch.object(RequestLog, 'log'):
        request_mock.return_value = Response()
        auth_manager = BasicAuthManager(TEST_API_USERNAME, TEST_API_PASSWORD)
        simple_request(
            domain=TEST_DOMAIN,
            url=TEST_API_URL,
            data='<payload id="abc123"><parrot status="déad" /></payload>',
            headers={'Content-Type': 'text/xml+parrot'},
            auth_manager=auth_manager,
            verify=True,
            payload_id=TEST_PAYLOAD_ID,
            method="PUT"
        )

        request_mock.assert_called_with(
            'PUT',
            TEST_API_URL,
            data=b'<payload id="abc123"><parrot status="d\xc3\xa9ad" /></payload>',
            headers={
                'Content-Type': 'text/xml+parrot',
                'content-length': '56',
            },
            json=None,
            timeout=REQUEST_TIMEOUT,
        )


def test_simple_request_DELETE():
    with patch.object(requests.Session, 'request') as request_mock, \
         patch.object(RequestLog, 'log'):
        request_mock.return_value = Response()
        auth_manager = BasicAuthManager(TEST_API_USERNAME, TEST_API_PASSWORD)
        simple_request(
            domain=TEST_DOMAIN,
            url=TEST_API_URL,
            data='<payload id="abc123"><parrot status="déad" /></payload>',
            headers={'Content-Type': 'text/xml+parrot'},
            auth_manager=auth_manager,
            verify=True,
            payload_id=TEST_PAYLOAD_ID,
            method="DELETE"
        )

        request_mock.assert_called_with(
            'DELETE',
            TEST_API_URL,
            data=b'<payload id="abc123"><parrot status="d\xc3\xa9ad" /></payload>',
            headers={
                'Content-Type': 'text/xml+parrot',
                'content-length': '56',
            },
            timeout=REQUEST_TIMEOUT,
        )


def test_simple_post():
    with patch.object(requests.Session, 'request') as request_mock, \
            patch.object(RequestLog, 'log') as log_mock:
        request_mock.return_value = Response()
        auth_manager = BasicAuthManager(TEST_API_USERNAME, TEST_API_PASSWORD)
        response = simple_post(
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
        assert_equal(response.status_code, 200)


def test_simple_post_400():
    with patch.object(requests.Session, 'request') as request_mock, \
            patch.object(Requests, 'notify_error') as notify_mock, \
            patch.object(RequestLog, 'log'):
        response = Response()
        response.status_code = 400
        response.content = b'Bad request'
        request_mock.return_value = response
        auth_manager = BasicAuthManager(TEST_API_USERNAME, TEST_API_PASSWORD)
        response = simple_post(
            domain=TEST_DOMAIN,
            url=TEST_API_URL,
            data='<payload id="abc123"><parrot status="déad" /></payload>',
            headers={'Content-Type': 'text/xml+parrot'},
            auth_manager=auth_manager,
            verify=True,
            payload_id=TEST_PAYLOAD_ID,
        )
        notify_mock.assert_called_with('HTTP status code 400: Bad request')
        assert_equal(response.status_code, 400)
