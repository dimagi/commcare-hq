from corehq.util.urlvalidate.urlvalidate import PossibleSSRFAttempt
from datetime import datetime
from unittest.mock import patch, ANY
from django.test import SimpleTestCase
from corehq.apps.sms.models import SMS, OUTGOING
from corehq.util.urlvalidate.test.mockipinfo import hostname_resolving_to_ips
from ..models import SQLHttpBackend
from .. import models


class TestHttpBackend(SimpleTestCase):
    backend_model = SQLHttpBackend

    @patch.object(models, 'urlopen')
    def test_sends_without_error(self, mock_urlopen):
        message = self._create_message(phone_number='1234567890', text='Hello World')
        backend = self._create_backend(url='http://www.dimagi.com')

        backend.send(message)
        mock_urlopen.assert_called_with('http://www.dimagi.com?message=Hello+World&number=1234567890',
            timeout=ANY)

    @hostname_resolving_to_ips('malicious.address', ['127.0.0.1'])
    @patch.object(SMS, 'save')  # mocked to avoid the database
    def test_throws_error_when_url_is_ssrf(self, mock_save):
        message = self._create_message()
        backend = self._create_backend(url='http://malicious.address')

        with self.assertRaises(PossibleSSRFAttempt):
            backend.send(message)

    def _create_backend(self, url='http://www.dimagi.com',
            message_param='message', number_param='number', method='GET'):
        return self.backend_model(extra_fields={
            'url': url,
            'message_param': message_param,
            'number_param': number_param,
            'include_plus': False,
            'method': method
        })

    def _create_message(self,
            domain='test_domain',
            phone_number='1234567890',
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
