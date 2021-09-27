from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.sms.models import SMS
from corehq.util.urlvalidate.test.mockipinfo import hostname_resolving_to_ips
from corehq.util.urlvalidate.urlvalidate import PossibleSSRFAttempt

from .. import sms_sending
from ..models import SQLHttpBackend
from ..sms_sending import verify_sms_url


class TestVerifySmsUrl(SimpleTestCase):
    def setUp(self):
        self.message = SMS()
        self.backend = SQLHttpBackend()

    @hostname_resolving_to_ips('www.dimagi.com', ['104.21.5.42'])
    def test_passes_valid_urls(self):
        verify_sms_url('https://www.diamgi.com', self.message, self.backend)

    @hostname_resolving_to_ips('malicious.address', ['127.0.0.1'])
    @patch.object(sms_sending, 'metrics_counter')
    @patch.object(SMS, 'save')
    def test_correctly_handles_ssrf(self, mock_save, mock_metrics_counter):
        # SSRF needs to:
        # - set the error on the message and save, so the message isn't re-queued
        # - generate a metric
        # - raise a PossibleSSRFAttempt exception

        message = SMS(domain='test-domain')

        # raise exception
        with self.assertRaises(PossibleSSRFAttempt):
            verify_sms_url('https://malicious.address', message, self.backend)

        # setting error message and saving
        self.assertTrue(message.error)
        self.assertEqual(message.system_error_message, 'FAULTY_GATEWAY_CONFIGURATION')
        mock_save.assert_called()

        # generating the metric
        mock_metrics_counter.assert_called_with('commcare.sms.ssrf_attempt',
            tags={'domain': 'test-domain', 'src': 'SQLHttpBackend', 'reason': 'is_loopback'})
