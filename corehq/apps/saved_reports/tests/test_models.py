from django.test import SimpleTestCase
from unittest.mock import create_autospec, patch, PropertyMock
from corehq.apps.users.models import WebUser
from corehq.apps.saved_reports import models
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


class TestRecipientsByLanguage(SimpleTestCase):
    def test_existing_user_with_no_language_gets_default_language(self):
        report = self._create_report_for_emails('test@dimagi.com')
        self._establish_user_languages([{'username': 'test@user.com', 'language': None}])

        recipients_by_language = report.recipients_by_language
        self.assertSetEqual(set(recipients_by_language.keys()), {'en'})
        self.assertSetEqual(set(recipients_by_language['en']), {'test@dimagi.com'})

    def test_missing_user_gets_default_language(self):
        report = self._create_report_for_emails('test@dimagi.com')
        self._establish_user_languages([])

        recipients_by_language = report.recipients_by_language
        self.assertSetEqual(set(recipients_by_language.keys()), {'en'})
        self.assertSetEqual(set(recipients_by_language['en']), {'test@dimagi.com'})

    def setUp(self):
        owner_patcher = patch.object(ReportNotification, 'owner_email', new_callable=PropertyMock)
        self.mock_owner_email = owner_patcher.start()
        self.mock_owner_email.return_value = 'owner@dimagi.com'
        self.addCleanup(owner_patcher.stop)

        user_doc_patcher = patch.object(models, 'get_user_docs_by_username')
        self.mock_get_user_docs = user_doc_patcher.start()
        self.addCleanup(user_doc_patcher.stop)

    def _create_report_for_emails(self, *emails):
        return ReportNotification(owner_id='owner@dimagi.com',
            domain='test_domain', recipient_emails=list(emails), send_to_owner=False)

    def _establish_user_languages(self, language_pairs):
        self.mock_get_user_docs.return_value = language_pairs
