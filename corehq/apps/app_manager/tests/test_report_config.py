from django.test import SimpleTestCase

from corehq.apps.app_manager.models import ReportAppConfig


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
