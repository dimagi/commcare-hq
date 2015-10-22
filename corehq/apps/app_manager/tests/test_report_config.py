from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2

from corehq.apps.app_manager.models import ReportAppConfig, Application, ReportModule, \
    ReportGraphConfig, ReportAppFilter
from corehq.apps.app_manager.tests import TestXmlMixin
from dimagi.utils import make_uuid


class ReportAppConfigTest(SimpleTestCase):

    def test_new_uuid(self):
        report_app_config = ReportAppConfig(report_id='report_id')
        self.assertTrue(report_app_config.uuid)
        self.assertIsInstance(report_app_config.uuid, basestring)

    def test_different_uuids(self):
        report_app_config_1 = ReportAppConfig(report_id='report_id')
        report_app_config_2 = ReportAppConfig(report_id='report_id')
        self.assertNotEqual(report_app_config_1.uuid, report_app_config_2.uuid)

    def test_existing_uuid(self):
        existing_uuid = 'existing_uuid'
        self.assertEqual(
            existing_uuid,
            ReportAppConfig.wrap({
                "report_id": "report_id",
                "uuid": existing_uuid,
            }).uuid
        )


class ReportFiltersSuiteTest(SimpleTestCase, TestXmlMixin):
    @classmethod
    def setUpClass(cls):
        cls.report_id = make_uuid()
        cls.report_config_id = make_uuid()
        cls.domain = 'report-filter-test-domain'
        cls.app = Application.new_app(cls.domain, "Report Filter Test App", APP_V2)
        module = cls.app.add_module(ReportModule.new_module("Report Module", 'en'))
        module.report_configs.append(
            ReportAppConfig(
                report_id=cls.report_id,
                header={},
                description={},
                graph_configs={
                    '7451243209119342931': ReportGraphConfig(
                        series_configs={'count': {}}
                    )
                },
                filters={},
                uuid=cls.report_config_id,
            )
        )
        cls.suite = cls.app.create_suite()

    def test_filter_detail(self):
        pass
