from django.test import SimpleTestCase
from django.utils.safestring import SafeText

from ..models import TempCommCareUser


class TestTempUserUsernameInReport(SimpleTestCase):

    def test_unknown_user_generates_correct_template(self):
        user = TempCommCareUser('test_domain', 'unknown_user', 'id')
        html = user.username_in_report
        self.assertEqual(html, 'unknown_user <strong>[unregistered]</strong>')
        self.assertIsInstance(html, SafeText)

    def test_escapes_unknown_username(self):
        user = TempCommCareUser('test_domain', 'unknown&user', 'id')
        html = user.username_in_report
        self.assertEqual(html, 'unknown&amp;user <strong>[unregistered]</strong>')

    def test_demo_user_generates_correct_template(self):
        user = TempCommCareUser('test_domain', 'demo_user', 'id')
        html = user.username_in_report
        self.assertEqual(html, '<strong>demo_user</strong>')
        self.assertIsInstance(html, SafeText)

    def test_admin_user_generates_correct_template(self):
        user = TempCommCareUser('test_domain', 'admin', 'id')
        html = user.username_in_report
        self.assertEqual(html, '<strong>admin</strong> (id)')
        self.assertIsInstance(html, SafeText)
