from django.test import TestCase

from corehq.apps.app_manager.models import LinkedApplication
from corehq.apps.linked_domain.applications import get_linked_apps_for_domain
from corehq.apps.linked_domain.ucr import get_linked_reports_in_domain
from corehq.apps.userreports.models import ReportConfiguration, ReportMeta
from corehq.apps.userreports.tests.utils import get_sample_data_source


class ApplicationUtilTests(TestCase):

    def test_get_linked_apps_for_domain(self):
        linked_app1 = LinkedApplication.new_app('domain', 'One')
        linked_app2 = LinkedApplication.new_app('domain', 'Two')
        linked_app1.save()
        linked_app2.save()
        self.addCleanup(linked_app1.delete)
        self.addCleanup(linked_app2.delete)

        linked_apps = get_linked_apps_for_domain('domain')
        linked_app_ids = [app._id for app in linked_apps]
        self.assertEqual([linked_app1._id, linked_app2._id], linked_app_ids)


class ReportHelperTests(TestCase):

    domain = 'domain'

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

    def test_get_linked_reports_in_domain(self):
        linked_report1 = self._create_report(master_id='abc123')
        linked_report2 = self._create_report(master_id='def456')

        linked_reports = get_linked_reports_in_domain(self.domain)
        linked_report_ids = [report._id for report in linked_reports]
        self.assertEqual([linked_report1._id, linked_report2._id], linked_report_ids)
