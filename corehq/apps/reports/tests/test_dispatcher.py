from django.test import SimpleTestCase, TestCase
from corehq.apps.domain.shortcuts import create_domain

from ..dispatcher import ProjectReportDispatcher, AdminReportDispatcher, DomainReportDispatcher


class ProjectReportDispatcherTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()

    def test_no_domain_has_no_reports(self):
        reports = list(ProjectReportDispatcher.get_reports(None))
        self.assertEqual(reports, [])

    def test_new_domain_contains_core_reports(self):
        reports = list(ProjectReportDispatcher.get_reports('test-domain'))
        monitor_worker_reports = reports[0]
        inspect_data_reports = reports[1]
        manage_deployment_reports = reports[2]
        messaging_reports = reports[3]

        self.assertEqual(monitor_worker_reports[0], 'Monitor Workers')
        self.assertEqual(inspect_data_reports[0], 'Inspect Data')
        self.assertEqual(manage_deployment_reports[0], 'Manage Deployments')
        self.assertEqual(messaging_reports[0], 'Messaging')

    def test_get_report_returns_none_if_not_found(self):
        report = ProjectReportDispatcher.get_report('test-domain', 'bad-report')
        self.assertIsNone(report)

    def test_get_report_returns_found_report(self):
        report = ProjectReportDispatcher.get_report('test-domain', 'worker_activity')
        self.assertEqual(report.slug, 'worker_activity')


class AdminReportDispatcherTests(SimpleTestCase):
    def test_get_reports_returns_all_admin_reports(self):
        report_groups = list(AdminReportDispatcher.get_reports(None))

        self.assertEqual(len(report_groups), 1)
        name, domain_stat_reports = report_groups[0]
        self.assertEqual(name, 'Domain Stats')
        report_names = {report.slug for report in domain_stat_reports}
        self.assertEqual(report_names, {
            'user_list_report',
            'user_audit_report',
            'device_log_soft_asserts',
            'deploy_history_report',
            'phone_number_report'
        })


class DomainReportDispatcherTests(SimpleTestCase):
    def test_get_reports_returns_correct_report_names(self):
        report_groups = list(DomainReportDispatcher.get_reports(None))

        self.assertEqual(len(report_groups), 1)
        name, project_settings_reports = report_groups[0]
        self.assertEqual(name, 'Project Settings')
        report_names = {report.slug for report in project_settings_reports}
        self.assertEqual(report_names, {
            'repeat_record_report',
            'project_link_report',
            'api_request_log_report'
        })
