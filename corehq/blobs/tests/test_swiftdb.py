from __future__ import absolute_import
from __future__ import unicode_literals

import re
from io import BytesIO

import requests_mock
from django.test import TestCase

from corehq.blobs.tests.test_fsdb import _BlobDBTests
from corehq.blobs.tests.util import TemporarySwiftBlobDB

DEFAULT_CONTENT = b'content'

URL = 'http://swift.test/v1/AUTH_mowcdmumusr'


def assert_body_equal(test, expected):
    def _assert(request, context):
        test.assertEquals(list(request.body), [expected])
    return _assert


def assert_copy_headers(test):
    def _assert(request, context):
        test.assertIn('destination', request.headers)
    return _assert


def mock_put(test, mock, content=DEFAULT_CONTENT):
    mock.put(test._url(match_any=True), text=assert_body_equal(test, content))


def mock_get(test, mock, content=DEFAULT_CONTENT):
    mock.get(test._url(match_any=True), body=BytesIO(DEFAULT_CONTENT), headers={
        'Content-Length': str(len(content))
    })


def mock_head(test, mock, content=DEFAULT_CONTENT):
    mock.head(test._url(match_any=True), headers={
        'Content-Length': str(len(content))
    })


@requests_mock.mock()
class TestSwiftBlobDB(TestCase, _BlobDBTests):

    @classmethod
    def setUpClass(cls):
        super(TestSwiftBlobDB, cls).setUpClass()
        config = {
            'authurl': 'https://swift.test/auth/v1.0/',
            'user': 'test',
            'preauthurl': URL,
            'preauthtoken': 'token',
            'container': 'test'
        }
        cls.db = TemporarySwiftBlobDB(config)

    def _url(self, object=None, match_any=False):
        regex = False
        url = '{}/{}'.format(URL, self.db.container)
        if match_any:
            assert not object
            object = '.*'
            regex = True
        if object:
            url = '{}/{}'.format(url, object)
        return re.compile(url) if regex else url

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(TestSwiftBlobDB, cls).tearDownClass()

    def test_put_and_get(self, mock):
        mock_put(self, mock)
        mock_get(self, mock)
        super(TestSwiftBlobDB, self).test_put_and_get()

    def test_put_and_size(self, mock):
        mock_put(self, mock)
        mock_head(self, mock)
        super(TestSwiftBlobDB, self).test_put_and_size()

    def test_put_with_timeout(self, mock):
        mock_put(self, mock)
        mock_get(self, mock)
        super(TestSwiftBlobDB, self).test_put_with_timeout()

    def test_put_and_get_with_unicode_names(self, mock):
        mock_put(self, mock)
        mock_get(self, mock)
        super(TestSwiftBlobDB, self).test_put_and_get_with_unicode_names()

    def test_put_from_get_stream(self, mock):
        mock_put(self, mock)
        mock.get(self._url(match_any=True), [
            {'body': BytesIO(DEFAULT_CONTENT), 'headers': {'Content-Length': str(len(DEFAULT_CONTENT))}},
            {'body': BytesIO(DEFAULT_CONTENT), 'headers': {'Content-Length': str(len(DEFAULT_CONTENT))}},
        ])
        mock_head(self, mock)
        mock.request('COPY', self._url(match_any=True), text=assert_copy_headers(self))
        super(TestSwiftBlobDB, self).test_put_from_get_stream()
