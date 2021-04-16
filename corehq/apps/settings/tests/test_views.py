from django.test import SimpleTestCase
from unittest.mock import Mock, patch

from corehq.apps.settings.views import EnableMobilePrivilegesView


class EnableMobilePrivilegesViewTests(SimpleTestCase):

    def test_qr_code(self):
        """
        Check that the qr code in the context is a string, as opposed to a byte object
        """
        view = EnableMobilePrivilegesView()
        view.get_context_data = Mock(return_value={})
        view.render_to_response = lambda x: x
        mock_request = Mock()
        mock_request.user.username = "test"

        with patch('corehq.apps.settings.views.sign', lambda x: b'foo'):
            context = view.get(mock_request)

        self.assertTrue(isinstance(context['qrcode_64'], str))
