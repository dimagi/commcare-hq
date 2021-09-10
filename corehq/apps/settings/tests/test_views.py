from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from unittest.mock import Mock, patch

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.settings.views import EnableMobilePrivilegesView
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.models import WebUser, UserHistory
from corehq.const import USER_CHANGE_VIA_WEB


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


class TestMyAccountSettingsView(TestCase):
    domain_name = 'test'

    def setUp(self):
        super().setUp()
        self.domain = create_domain(self.domain_name)
        self.couch_user = WebUser.create(None, "test", "foobar", None, None)
        self.couch_user.add_domain_membership(self.domain_name, is_admin=True)
        self.couch_user.save()

        self.url = reverse('my_account_settings')
        self.client.login(username='test', password='foobar')

    def tearDown(self):
        self.couch_user.delete(self.domain_name, deleted_by=None)
        self.domain.delete()
        super().tearDown()

    def test_process_delete_phone_number(self):
        phone_number = "9999999999"
        self.client.post(
            self.url,
            {"form_type": "delete-phone-number", "phone_number": phone_number}
        )

        user_history_log = UserHistory.objects.get(user_id=self.couch_user.get_id)
        self.assertIsNone(user_history_log.message)
        self.assertEqual(user_history_log.change_messages, UserChangeMessage.phone_numbers_removed([phone_number]))
        self.assertEqual(user_history_log.changed_by, self.couch_user.get_id)
        self.assertIsNone(user_history_log.domain)
        self.assertEqual(user_history_log.changed_via, USER_CHANGE_VIA_WEB)
