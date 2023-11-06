from datetime import datetime, timedelta
from django.http.request import QueryDict
from django.test import SimpleTestCase, TestCase
from smtplib import SMTPSenderRefused
from dimagi.utils.dates import DateSpan
from dimagi.utils.django.email import LARGE_FILE_SIZE_ERROR_CODE
from unittest.mock import create_autospec, patch, PropertyMock, ANY
from corehq.apps.reports import views
from corehq.apps.users.models import CouchUser, WebUser
from corehq.apps.saved_reports import models
from corehq.apps.saved_reports.tasks import create_config_for_email
from ..models import ReportNotification, ReportConfig


class TestReportConfig(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.user_id = 'nothing'
        cls.report_slug = 'case_list_explorer'
        cls.report_type = 'project_report'

        GET = {'send_to_owner': 'true',
               'subject': 'Case List Explorer',
               'getReportRenderUrl':
                   '/a/test-domain/reports/undefined/case_list_explorer/?search_xpath=case_name%3D%22EXAMPLEXPATH'
                   '%22&explorer_columns=%5B%7B%22name%22%3A%22%40case_type%22%2C%22label%22%3A%22%40case_type'
                   '%22%7D%2C%7B%22name%22%3A%22case_name%22%2C%22label%22%3A%22case_name%22%7D%2C%7B%22name'
                   '%22%3A%22last_modified%22%2C%22label%22%3A%22last_modified'
                   '%22%7D%5D&case_list_filter=project_data&case_type=&is_open=',
               'params':
                   'search_xpath=case_name%3D%22EXAMPLEXPATH%22&explorer_columns=%5B%7B%22name'
                   '%22%3A%22%40case_type%22%2C%22label%22%3A%22%40case_type%22%7D%2C%7B%22name'
                   '%22%3A%22case_name%22%2C%22label%22%3A%22case_name%22%7D%2C%7B%22name'
                   '%22%3A%22last_modified%22%2C%22label%22%3A%22last_modified'
                   '%22%7D%5D&case_list_filter=project_data&case_type=&is_open='
               }
        GET_dict = QueryDict('', mutable=True)
        GET_dict.update(GET)
        test_date = datetime(2023, 7, 25)

        cls.request_data = {
            'GET': GET_dict,
            'META': {'QUERY_STRING': '', 'PATH_INFO': '/a/test-domain/reports/email_onceoff/case_list_explorer/'},
            'datespan': DateSpan(
                startdate=test_date - timedelta(days=30),
                enddate=test_date
            ),
            'couch_user': cls.user_id,
            'can_access_all_locations': True
        }

    def test_report_is_shared_on_domain(self):
        self.config = ReportConfig(
            domain=self.domain,
        )
        self.addCleanup(self.config.delete)
        self.config.save()
        self.assertFalse(self.config.is_shared_on_domain())

    def test_report_config_contents(self):
        self.config = create_config_for_email(
            self.report_type, self.report_slug, self.user_id, self.domain, self.request_data
        )
        self.config.save()
        self.addCleanup(self.config.delete)
        self.assertEqual(self.config.filters.get('search_xpath'), 'case_name="EXAMPLEXPATH"')
        self.assertEqual(self.config.filters.get('explorer_columns'),
                         '[{"name":"@case_type","label":"@case_type"},'
                         '{"name":"case_name","label":"case_name"},'
                         '{"name":"last_modified","label":"last_modified"}]')

    def test_report_config_does_not_have_datespan_if_not_in_params(self):
        self.config = create_config_for_email(
            self.report_type, self.report_slug, self.user_id, self.domain, self.request_data
        )
        self.config.save()
        self.addCleanup(self.config.delete)
        self.assertEqual(self.config.filters.get('startdate'), None)
        self.assertEqual(self.config.filters.get('enddate'), None)


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

    def test_report_with_unknown_owner_has_null_owner_email(self):
        report = ReportNotification(owner_id='5', domain='test_domain')
        with patch.object(CouchUser, "get_by_user_id", lambda uid: None):
            self.assertIsNone(report.owner)
            self.assertIsNone(report.owner_email)

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
        self.assertEqual(recipients_by_language, {'en': ['test@dimagi.com']})

    def test_missing_user_gets_default_language(self):
        report = self._create_report_for_emails('test@dimagi.com')
        self._establish_user_languages([])

        recipients_by_language = report.recipients_by_language
        self.assertEqual(recipients_by_language, {'en': ['test@dimagi.com']})

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


class TestGetAndSendReport(SimpleTestCase):
    @patch.object(views, 'get_scheduled_report_response')
    @patch.object(ReportNotification, 'owner', new_callable=PropertyMock)
    def test_failing_report_generation_generates_log_message(self, owner_mock, mock_get_scheduled_report_response):
        owner_mock.return_value = WebUser(username='test user')
        mock_get_scheduled_report_response.side_effect = Exception('report generation failed!')
        report = ReportNotification(owner_id='owner@dimagi.com',
            domain='test_domain', recipient_emails=['test@dimagi.com'], send_to_owner=False)

        with self.assertLogs('notify', level='ERROR') as cm:
            report._get_and_send_report('en', ['test@dimagi.com'])
            self.assertIn('Encountered error while generating report', cm.output[0])


class TestSendEmails(SimpleTestCase):
    def setUp(self):
        email_mocker = patch.object(models, 'send_HTML_email')
        self.mock_send_email = email_mocker.start()
        self.addCleanup(email_mocker.stop)

        logger_mocker = patch.object(models, 'ScheduledReportLogger')
        self.report_logger = logger_mocker.start()
        self.addCleanup(logger_mocker.stop)

    def test_each_email_is_sent(self):
        ARG_INDEX = 0
        EMAIL_INDEX = 1
        report = ReportNotification(_id='5', domain='test-domain', uuid='uuid')
        report._send_emails('Test Report', 'Report Text', ['test1@dimagi.com', 'test2@dimagi.com'], excel_files=[])
        emails = {call_args[ARG_INDEX][EMAIL_INDEX] for call_args in self.mock_send_email.call_args_list}
        self.assertSetEqual(emails, {'test1@dimagi.com', 'test2@dimagi.com'})

    def test_successful_emails_are_logged(self):
        report = ReportNotification(_id='5', domain='test-domain', uuid='uuid')

        report._send_emails('Test Report', 'Report Text',
            ['test1@dimagi.com', 'test2@dimagi.com'], excel_files=[])
        self.report_logger.log_email_success.assert_any_call(report, 'test1@dimagi.com', ANY)
        self.report_logger.log_email_success.assert_any_call(report, 'test2@dimagi.com', ANY)

    @patch.object(ReportNotification, '_export_report')
    def test_emails_that_are_too_large_are_exported(self, mock_export_report):
        self.mock_send_email.side_effect = SMTPSenderRefused(code=LARGE_FILE_SIZE_ERROR_CODE, msg='test error',
            sender='admin@dimagi.com')
        report = ReportNotification(_id='5', domain='test-domain', uuid='uuid')

        report._send_emails('Test Report', 'Report Text',
            ['test1@dimagi.com', 'test2@dimagi.com'], excel_files=[])
        mock_export_report.assert_called()
        self.report_logger.log_email_size_failure.assert_called_with(
            report, 'test1@dimagi.com', ['test1@dimagi.com', 'test2@dimagi.com'], ANY)

    @patch.object(ReportNotification, '_export_report')
    def test_emails_that_are_too_large_stop_after_first_failure(self, mock_export_report):
        self.mock_send_email.side_effect = SMTPSenderRefused(code=LARGE_FILE_SIZE_ERROR_CODE, msg='test error',
            sender='admin@dimagi.com')
        report = ReportNotification(_id='5', domain='test-domain', uuid='uuid')

        report._send_emails('Test Report', 'Report Text',
            ['test1@dimagi.com', 'test2@dimagi.com'], excel_files=[])

        self.mock_send_email.assert_called_once()

    def test_huge_reports_with_attachments_resend_only_attachments(self):
        # trigger the exception on the first call, success on the second
        # (a failure needs to occur to trigger the re-send)
        self.mock_send_email.side_effect = [SMTPSenderRefused(code=LARGE_FILE_SIZE_ERROR_CODE, msg='test error',
            sender='admin@dimagi.com'), None]
        report = ReportNotification(_id='5', domain='test-domain', uuid='uuid')
        report._send_emails('Test Report', 'Report Text',
            ['test1@dimagi.com', 'test2@dimagi.com'], excel_files=['abba'])

        self.mock_send_email.assert_called_with('Test Report',
            ['test1@dimagi.com', 'test2@dimagi.com'],
            'Unable to generate email report. Excel files are attached.',
            file_attachments=['abba'],
            domain='test-domain', use_domain_gateway=True)

    def test_failing_emails_are_logged(self):
        self.mock_send_email.side_effect = Exception('Email failed to send')
        report = ReportNotification(_id='5', domain='test-domain', uuid='uuid')

        report._send_emails('Test Report', 'Report Text',
            ['test1@dimagi.com', 'test2@dimagi.com'], excel_files=[])

        calls = self.report_logger.log_email_failure.call_args_list

        self.assertEqual(calls[0][0][0], report)
        self.assertEqual(calls[0][0][1], 'test1@dimagi.com')
        self.assertEqual(str(calls[0][0][3]), 'Email failed to send')

        self.assertEqual(calls[1][0][0], report)
        self.assertEqual(calls[1][0][1], 'test2@dimagi.com')
        self.assertEqual(str(calls[1][0][3]), 'Email failed to send')
