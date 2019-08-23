# encoding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from six.moves.urllib.parse import parse_qs, urlparse

from mock import patch

from django.test import SimpleTestCase

from corehq.apps.sms.models import SMS
from corehq.messaging.smsbackends.unicel.models import SQLUnicelBackend


class TestUnicelSend(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestUnicelSend, cls).setUpClass()
        cls.backend = SQLUnicelBackend()

    def test_sending_ascii(self):
        self._test_unicel_send('ascii', 'ascii')

    def test_sending_utf8(self):
        self._test_unicel_send('útf-8', '00FA00740066002D0038')

    def _test_unicel_send(self, text, expected_msg):
        message = SMS(text=text, phone_number='+15555555555')
        with patch('corehq.messaging.smsbackends.unicel.models.urlopen') as patch_urlopen:
            self.backend.send(message)
        self.assertEqual(len(patch_urlopen.call_args_list), 1)
        called_args = patch_urlopen.call_args_list[0]
        url, = called_args[0]
        parsed_url = urlparse(url)
        url_params = parse_qs(parsed_url.query)
        self.assertEqual(url_params['msg'], [expected_msg])
