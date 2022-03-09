from corehq.util.urlvalidate.urlvalidate import PossibleSSRFAttempt
from corehq.util.urlvalidate.test.mockipinfo import hostname_resolving_to_ips
from datetime import datetime
from django.test import SimpleTestCase
from unittest.mock import patch, MagicMock, ANY
from corehq.apps.sms.models import OUTGOING, SMS
from ..models import SQLAppositBackend
from .. import models


class TestSqlAppositBackend(SimpleTestCase):
    def test_sends_message(self):
        message = self._create_message(phone_number='2511234567', text='Hello!')
        backend = self._create_backend(host='www.dimagi.com', from_number='1234567890')

        self._set_post_success_id('123')
        backend.send(message)

        self.mock_post.assert_called_with('https://www.dimagi.com/mmp/api/v2/json/sms/send',
            auth=ANY,
            data='{"from": "1234567890", "to": "2511234567", "message": "Hello!"}',
            headers=ANY,
            timeout=ANY)
        self.assertEqual(message.backend_message_id, '123')

    @hostname_resolving_to_ips('malicious.address', ['127.0.0.1'])
    def test_rejects_ssrf_exceptions(self):
        message = self._create_message()
        backend = self._create_backend(host='malicious.address')

        with self.assertRaises(PossibleSSRFAttempt):
            backend.send(message)

    ############################################################

    def setUp(self):
        post_patcher = patch.object(models.requests, 'post')
        self.mock_post = post_patcher.start()
        self.addCleanup(post_patcher.stop)

        # Mock save calls to allow us to avoid the database
        save_patcher = patch.object(SMS, 'save')
        save_patcher.start()
        self.addCleanup(save_patcher.stop)

    def _set_post_success_id(self, id):
        response = MagicMock()
        response.json.return_value = {
            'statusCode': 0,
            'messageId': id
        }
        self.mock_post.return_value = response

    def _create_backend(self, host='www.dimagi.com', from_number='123'):
        return SQLAppositBackend(
            extra_fields={
                'host': host,
                'from_number': from_number
            }
        )

    def _create_message(self,
            domain='test_domain',
            phone_number='2511234567',
            direction=OUTGOING,
            date=None,
            text='Hello World'):
        if not date:
            date = datetime(2021, 5, 15)

        return SMS(
            domain=domain,
            phone_number=phone_number,
            direction=direction,
            date=date,
            text=text
        )
