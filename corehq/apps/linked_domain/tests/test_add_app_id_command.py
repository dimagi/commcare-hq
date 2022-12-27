import uuid

from django.test.testcases import TestCase

from corehq.apps.app_manager.models import Application, LinkedApplication
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.management.commands.add_app_id_to_linked_reports import (
    migrate_linked_reports,
)
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
    ReportMeta,
)


class TestAddAppIdToLinkedReports(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestAddAppIdToLinkedReports, cls).setUpClass()
        cls.upstream_domain_obj = create_domain('test-upstream')
        cls.addClassCleanup(cls.upstream_domain_obj.delete)
        cls.upstream_domain = cls.upstream_domain_obj.name

        cls.downstream_domain_obj = create_domain('test-downstream')
        cls.addClassCleanup(cls.downstream_domain_obj.delete)
        cls.downstream_domain = cls.downstream_domain_obj.name

        cls.domain_link = DomainLink.link_domains(cls.downstream_domain, cls.upstream_domain)

        cls.original_app = Application.new_app(cls.upstream_domain, "Original Application")
        cls.original_app.linked_whitelist = [cls.downstream_domain]
        cls.original_app.save()
        cls.addClassCleanup(cls.original_app.delete)

        cls.linked_app = LinkedApplication.new_app(cls.downstream_domain, "Linked Application")
        cls.linked_app.upstream_app_id = cls.original_app._id
        cls.linked_app.family_id = cls.original_app._id
        cls.linked_app.save()
        cls.addClassCleanup(cls.linked_app.delete)

        cls.original_report = cls._create_report(cls.upstream_domain, app_id=cls.original_app._id)
        # intentionally do not pass app_id into create method, as this is the scenario this migration is used in
        cls.linked_report = cls._create_report(cls.downstream_domain, upstream_id=cls.original_report._id)

    def test_app_id_for_linked_reports_updates_given_upstream_app_id(self):
        self.linked_report.config.meta.build.app_id = None
        self.linked_report.save()
        self.assertIsNone(self.linked_report.config.meta.build.app_id)
        self.linked_app.family_id = None
        self.linked_app.upstream_app_id = self.original_app._id
        self.linked_app.save()

        num_of_failed_attempts = migrate_linked_reports()
        self.assertEqual(0, num_of_failed_attempts)
        # refetch
        actual_report = ReportConfiguration.get(self.linked_report._id)
        self.assertEqual(self.linked_app._id, actual_report.config.meta.build.app_id)

    def test_app_id_for_linked_reports_updates_given_family_id(self):
        self.linked_report.config.meta.build.app_id = None
        self.linked_report.save()
        self.assertIsNone(self.linked_report.config.meta.build.app_id)
        self.linked_app.family_id = self.original_app._id
        self.linked_app.upstream_app_id = None
        self.linked_app.save()

        num_of_failed_attempts = migrate_linked_reports()
        self.assertEqual(0, num_of_failed_attempts)
        # refetch
        actual_report = ReportConfiguration.get(self.linked_report._id)
        self.assertEqual(self.linked_app._id, actual_report.config.meta.build.app_id)

    def test_app_id_for_linked_reports_increments_failed_attempts(self):
        self.linked_report.config.meta.build.app_id = None
        self.linked_report.save()
        self.assertIsNone(self.linked_report.config.meta.build.app_id)
        self.linked_app.family_id = None
        self.linked_app.upstream_app_id = None
        self.linked_app.save()

        num_of_failed_attempts = migrate_linked_reports()
        self.assertEqual(1, num_of_failed_attempts)

    def test_linked_report_with_app_id_is_not_updated(self):
        self.linked_report.config.meta.build.app_id = self.linked_app._id
        self.linked_report.save()
        self.assertEqual(self.linked_app._id, self.linked_report.config.meta.build.app_id)
        num_of_failed_attempts = migrate_linked_reports()
        self.assertEqual(0, num_of_failed_attempts)
        # refetch
        actual_report = ReportConfiguration.get(self.linked_report._id)
        self.assertEqual(self.linked_app._id, actual_report.config.meta.build.app_id)

    @classmethod
    def _create_report(cls, domain, title="report", upstream_id=None, app_id=None):
        data_source = DataSourceConfiguration(
            domain=domain,
            table_id=uuid.uuid4().hex,
            referenced_doc_type='XFormInstance',
        )
        data_source.meta.build.app_id = app_id
        data_source.save()
        cls.addClassCleanup(data_source.delete)
        report = ReportConfiguration(
            domain=domain,
            config_id=data_source._id,
            title=title,
            report_meta=ReportMeta(created_by_builder=True,
                                   master_id=upstream_id),
        )

        report.save()
        cls.addClassCleanup(report.delete)

        return report
