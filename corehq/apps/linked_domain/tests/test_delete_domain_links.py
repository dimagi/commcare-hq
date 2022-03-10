from django.test import TestCase, SimpleTestCase

from corehq.apps.app_manager.models import Application, LinkedApplication
from corehq.apps.linked_domain.applications import unlink_app, unlink_apps_in_domain
from corehq.apps.linked_domain.keywords import unlink_keyword, unlink_keywords_in_domain
from corehq.apps.linked_domain.ucr import unlink_report, unlink_reports_in_domain
from corehq.apps.sms.models import Keyword
from corehq.apps.userreports.models import ReportMeta, ReportConfiguration
from corehq.apps.userreports.tests.utils import get_sample_data_source


class UnlinkApplicationTest(TestCase):

    domain = 'unlink-app-test'

    def test_unlink_app_returns_none_if_not_linked(self):
        app = Application.new_app(self.domain, 'Application')
        app.save()
        self.addCleanup(app.delete)

        unlinked_app = unlink_app(app)

        self.assertIsNone(unlinked_app)

    def test_unlink_app_returns_regular_app_if_linked(self):
        linked_app = LinkedApplication.new_app(self.domain, 'Linked Application')
        linked_app.family_id = 'abc123'
        linked_app.save()
        expected_app_id = linked_app._id

        unlinked_app = unlink_app(linked_app)
        self.addCleanup(unlinked_app.delete)

        # ensure new app is not linked, and converted properly
        self.assertEqual('Application', unlinked_app.get_doc_type())
        self.assertIsNone(unlinked_app.family_id)
        self.assertEqual(expected_app_id, unlinked_app._id)


class UnlinkApplicationsForDomainTests(TestCase):

    domain = 'unlink-apps-test'

    def test_unlink_apps_for_domain_successfully_unlinks_app(self):
        linked_app = LinkedApplication.new_app(self.domain, 'Linked')
        linked_app.save()
        expected_app_id = linked_app._id

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        # ensure new app exists that is not linked
        self.assertEqual('Application', unlinked_apps[0].get_doc_type())
        self.assertEqual(expected_app_id, unlinked_apps[0]._id)

    def test_unlink_apps_for_domain_processes_multiple_apps(self):
        linked_app1 = LinkedApplication.new_app(self.domain, 'Linked1')
        linked_app2 = LinkedApplication.new_app(self.domain, 'Linked2')
        linked_app1.save()
        linked_app2.save()

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        self.assertEqual(2, len(unlinked_apps))

    def test_unlink_apps_for_domain_only_processes_linked_apps(self):
        app = Application.new_app(self.domain, 'Original')
        linked_app = LinkedApplication.new_app(self.domain, 'Linked')
        app.save()
        self.addCleanup(app.delete)
        linked_app.save()
        expected_app_id = linked_app._id

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        self.assertEqual(1, len(unlinked_apps))
        self.assertEqual(expected_app_id, unlinked_apps[0]._id)

    def test_unlink_apps_for_domain_returns_zero_if_no_linked_apps(self):
        app = Application.new_app(self.domain, 'Original')
        app.save()
        self.addCleanup(app.delete)

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        self.assertEqual(0, len(unlinked_apps))


class UnlinkUCRTest(TestCase):

    domain = 'unlink-ucr-test'

    def test_unlink_ucr_returns_none_if_not_linked(self):
        report = ReportConfiguration()
        report.domain = self.domain
        report.config_id = '123abd'
        report.report_meta = ReportMeta()
        report.save()
        self.addCleanup(report.delete)

        unlinked_report = unlink_report(report)

        self.assertIsNone(unlinked_report)

    def test_unlink_ucr_returns_unlinked_report(self):
        report = ReportConfiguration()
        report.domain = self.domain
        report.config_id = '123abd'
        report.report_meta = ReportMeta(master_id='abc123')
        report.save()
        self.addCleanup(report.delete)

        unlinked_report = unlink_report(report)

        self.assertIsNone(unlinked_report.report_meta.master_id)


class UnlinkUCRsForDomainTests(TestCase):

    domain = 'unlink-ucrs-test'

    def _create_report(self, master_id=None):
        data_source = get_sample_data_source()
        data_source.domain = self.domain
        data_source.save()
        self.addCleanup(data_source.delete)

        report = ReportConfiguration()
        report.config_id = data_source.get_id
        report.domain = self.domain
        report.report_meta = ReportMeta()
        report.report_meta.master_id = master_id
        report.save()
        self.addCleanup(report.delete)
        return report

    def test_unlink_ucrs_in_domain_successfully_unlinks_report(self):
        report = self._create_report(master_id='abc123')

        unlinked_reports = unlink_reports_in_domain(self.domain)

        self.assertEqual(1, len(unlinked_reports))
        self.assertEqual(report._id, unlinked_reports[0]._id)

    def test_unlink_ucrs_in_domain_processes_multiple_linked_ucrs(self):
        linked_report1 = self._create_report(master_id='abc123')
        linked_report2 = self._create_report(master_id='def456')

        unlinked_reports = unlink_reports_in_domain(self.domain)

        self.assertEqual(2, len(unlinked_reports))
        report_ids = [report._id for report in unlinked_reports]
        self.assertEqual([linked_report1._id, linked_report2._id], report_ids)

    def test_unlink_ucrs_in_domain_only_processes_linked_ucrs(self):
        original_report = self._create_report()
        linked_report = self._create_report(master_id='abc123')

        unlinked_reports = unlink_reports_in_domain(self.domain)

        self.assertEqual(1, len(unlinked_reports))
        self.assertNotEqual(original_report._id, unlinked_reports[0]._id)
        self.assertEqual(linked_report._id, unlinked_reports[0]._id)

    def test_unlink_ucrs_in_domain_returns_zero_if_no_linked_ucrs(self):
        _ = self._create_report()

        unlinked_reports = unlink_reports_in_domain(self.domain)

        self.assertEqual(0, len(unlinked_reports))


class UnlinkKeywordTests(TestCase):

    def test_unlink_keyword_returns_none_if_not_linked(self):
        keyword = Keyword()
        keyword.save()

        unlinked_keyword = unlink_keyword(keyword)

        self.assertIsNone(unlinked_keyword)

    def test_unlink_keyword_returns_unlinked_keyword(self):
        keyword = Keyword(upstream_id='abc123')
        keyword.save()

        unlinked_keyword = unlink_keyword(keyword)

        self.assertIsNone(unlinked_keyword.upstream_id)
        self.assertEqual(keyword.id, unlinked_keyword.id)


class UnlinkKeywordsInDomainTests(TestCase):

    domain = 'unlink-keyword-test'

    def test_unlink_keywords_in_domain_successfully_unlinks_keyword(self):
        keyword = Keyword(domain=self.domain, upstream_id='abc123')
        keyword.save()

        unlinked_keywords = unlink_keywords_in_domain(self.domain)

        self.assertEqual(1, len(unlinked_keywords))
        self.assertIsNone(unlinked_keywords[0].upstream_id)
        self.assertEqual(keyword.id, unlinked_keywords[0].id)

    def test_unlink_keywords_in_domain_unlinks_multiple_keywords(self):
        keyword1 = Keyword(domain=self.domain, upstream_id='abc123')
        keyword2 = Keyword(domain=self.domain, upstream_id='abc123')
        keyword1.save()
        keyword2.save()

        unlinked_keywords = unlink_keywords_in_domain(self.domain)

        self.assertEqual(2, len(unlinked_keywords))
        self.assertIsNone(unlinked_keywords[0].upstream_id)
        self.assertIsNone(unlinked_keywords[1].upstream_id)
        keyword_ids = [keyword.id for keyword in unlinked_keywords]
        self.assertTrue(keyword1.id in keyword_ids)
        self.assertTrue(keyword2.id in keyword_ids)

    def test_unlink_keywords_in_domain_only_processes_linked_keywords(self):
        original_keyword = Keyword(domain=self.domain)
        linked_keyword = Keyword(domain=self.domain, upstream_id='abc123')
        original_keyword.save()
        linked_keyword.save()

        unlinked_keywords = unlink_keywords_in_domain(self.domain)

        self.assertEqual(1, len(unlinked_keywords))
        self.assertIsNone(unlinked_keywords[0].upstream_id)
        keyword_ids = [keyword.id for keyword in unlinked_keywords]
        self.assertFalse(original_keyword.id in keyword_ids)
        self.assertTrue(linked_keyword.id in keyword_ids)

    def test_unlink_keywords_in_domain_returns_zero_if_no_linked_keywords(self):
        keyword = Keyword(domain=self.domain)
        keyword.save()

        unlinked_keywords = unlink_keywords_in_domain(self.domain)

        self.assertEqual(0, len(unlinked_keywords))
