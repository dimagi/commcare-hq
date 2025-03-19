from unittest import mock
from unittest.mock import patch, MagicMock

from django.test import TestCase

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.enterprise import EnterpriseReport
from corehq.apps.enterprise.exceptions import EnterpriseReportError
from corehq.apps.enterprise.tasks import email_enterprise_report
from corehq.apps.users.models import WebUser


class TestEmailEnterpriseReport(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestEmailEnterpriseReport, cls).setUpClass()
        cls.domain = Domain.get_or_create_with_name('test', is_active=True)
        cls.couch_user = WebUser.create(cls.domain.name, "enterprise-tasks-tests", "*******", None, None,
                                        is_admin=True)
        cls.couch_user.save()
        cls.billing_account = BillingAccount.get_or_create_account_by_domain(cls.domain.name,
                                                                             created_by=cls.domain.name)[0]

    @classmethod
    def tearDownClass(cls):
        cls.billing_account.delete()
        cls.couch_user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super(TestEmailEnterpriseReport, cls).tearDownClass()

    @patch('corehq.apps.enterprise.tasks.send_html_email_async')
    def test_email_report_domains_successful(self, mock_send):
        """
        Test that a request to email a Domains enterprise report is successful
        """

        mock_redis_client = MagicMock()
        mock_redis_client.set.return_value = MagicMock(return_value=None)
        mock_redis_client.expire.return_value = MagicMock(return_value=None)

        with patch('corehq.apps.enterprise.tasks.get_redis_client', return_val=mock_redis_client):
            email_enterprise_report(self.domain.name, EnterpriseReport.DOMAINS, self.couch_user)

        expected_title = "Enterprise Dashboard: Project Spaces"
        mock_send.assert_called_with(expected_title, self.couch_user.username, mock.ANY,
                                     domain=self.domain.name, use_domain_gateway=True)

    @patch('corehq.apps.enterprise.tasks.send_html_email_async')
    def test_email_report_web_users(self, mock_send):
        """
        Test that a request to email a Web Users enterprise report is successful
        """

        mock_redis_client = MagicMock()
        mock_redis_client.set.return_value = MagicMock(return_value=None)
        mock_redis_client.expire.return_value = MagicMock(return_value=None)

        with patch('corehq.apps.enterprise.tasks.get_redis_client', return_val=mock_redis_client):
            email_enterprise_report(self.domain.name, EnterpriseReport.WEB_USERS, self.couch_user)

        expected_title = "Enterprise Dashboard: Web Users"
        mock_send.assert_called_with(expected_title, self.couch_user.username, mock.ANY,
                                     domain=self.domain.name, use_domain_gateway=True)

    @patch('corehq.apps.enterprise.tasks.send_html_email_async')
    def test_email_report_mobile_users(self, mock_send):
        """
        Test that a request to email a Mobile Users enterprise report is successful
        """

        mock_redis_client = MagicMock()
        mock_redis_client.set.return_value = MagicMock(return_value=None)
        mock_redis_client.expire.return_value = MagicMock(return_value=None)

        with patch('corehq.apps.enterprise.tasks.get_redis_client', return_val=mock_redis_client):
            email_enterprise_report(self.domain.name, EnterpriseReport.MOBILE_USERS, self.couch_user)

        expected_title = "Enterprise Dashboard: Mobile Workers"
        mock_send.assert_called_with(expected_title, self.couch_user.username, mock.ANY,
                                     domain=self.domain.name, use_domain_gateway=True)

    @patch('corehq.apps.enterprise.tasks.send_html_email_async')
    def test_email_report_form_submissions(self, mock_send):
        """
        Test that a request to email a Form Submissions enterprise report is successful
        """

        mock_redis_client = MagicMock()
        mock_redis_client.set.return_value = MagicMock(return_value=None)
        mock_redis_client.expire.return_value = MagicMock(return_value=None)

        with patch('corehq.apps.enterprise.tasks.get_redis_client', return_val=mock_redis_client):
            email_enterprise_report(self.domain.name, EnterpriseReport.FORM_SUBMISSIONS, self.couch_user)

        expected_title = "Enterprise Dashboard: Mobile Form Submissions"
        mock_send.assert_called_with(expected_title, self.couch_user.username, mock.ANY,
                                     domain=self.domain.name, use_domain_gateway=True)

    def test_email_report_unknown_type_fails(self):
        """
        Test that a request to email an enterprise report of an unknown type raises an EnterpriseReportError
        """

        mock_redis_client = MagicMock()
        mock_redis_client.set.return_value = MagicMock(return_value=None)
        mock_redis_client.expire.return_value = MagicMock(return_value=None)

        with patch('corehq.apps.enterprise.tasks.get_redis_client', return_val=mock_redis_client), \
                self.assertRaises(EnterpriseReportError):
            email_enterprise_report(self.domain.name, 'unknown', self.couch_user)
