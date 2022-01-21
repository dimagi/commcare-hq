import json

from django.test import SimpleTestCase
from unittest.mock import patch, MagicMock
from django.test.client import RequestFactory

from ...views.cli import direct_ccz
from ...views import cli


class DirectCCZTests(SimpleTestCase):
    def test_missing_app_id(self):
        rf = RequestFactory()
        request = rf.get('', {})
        response = direct_ccz(request, 'test-domain')

        self.assertEqual(response.status_code, 400)
        response_reason = json.loads(response.content)
        self.assertEqual(response_reason['message'], 'You must specify `app_id` in your GET parameters')

    @patch.object(cli, '_get_app', return_value=None)
    def test_missing_application_returns_404(self, mock_get_app):
        rf = RequestFactory()
        request = rf.get('', {'app_id': 'missing_id'})
        response = direct_ccz(request, 'test-domain')
        self.assertEqual(response.status_code, 404)

    @patch.object(cli, '_get_app')
    def test_invalid_application_returns_400(self, mock_get_app):
        invalid_app = MagicMock(copy_of=False, validate_app=lambda: ['some error'])
        mock_get_app.return_value = invalid_app

        rf = RequestFactory()
        request = rf.get('', {'app_id': 'some_id'})
        response = direct_ccz(request, 'test-domain')
        self.assertEqual(response.status_code, 400)
