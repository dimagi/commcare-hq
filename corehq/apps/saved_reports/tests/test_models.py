from django.test import SimpleTestCase
from unittest.mock import create_autospec
from corehq.apps.users.models import WebUser
from ..models import ReportNotification


class TestReportNotification(SimpleTestCase):
    def test_unauthorized_user_cannot_view_report(self):
        report = ReportNotification(owner_id='5', domain='test_domain', recipient_emails=[])
        bad_user = self._create_user(id='3', is_domain_admin=False)
        self.assertFalse(report.can_be_viewed_by(bad_user))

    def test_owner_can_view_report(self):
        report = ReportNotification(owner_id='5', domain='test_domain', recipient_emails=[])
        owner = self._create_user(id='5')
        self.assertTrue(report.can_be_viewed_by(owner))

    def test_domain_admin_can_view_report(self):
        report = ReportNotification(owner_id='5', domain='test_domain', recipient_emails=[])
        domain_admin = self._create_user(is_domain_admin=True)
        self.assertTrue(report.can_be_viewed_by(domain_admin))

    def test_subscribed_user_can_view_report(self):
        report = ReportNotification(owner_id='5', domain='test_domain', recipient_emails=['test@dimagi.com'])
        subscribed_user = self._create_user(email='test@dimagi.com')
        self.assertTrue(report.can_be_viewed_by(subscribed_user))

    def _create_user(self, id='100', email='not-included', is_domain_admin=False):
        user_template = WebUser(domain='test_domain', username='test_user')
        user = create_autospec(user_template, spec_set=True, _id=id)
        user.is_domain_admin = lambda domain: is_domain_admin
        user.get_email = lambda: email

        return user
