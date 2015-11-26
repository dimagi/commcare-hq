import os
from django.test import TestCase

from corehq.apps.receiverwrapper import submit_form_locally
from corehq.util.test_utils import TestFileMixin
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import run_with_all_backends
from phonelog.models import UserEntry, DeviceReportEntry


class DeviceLogTest(TestCase, TestFileMixin):
    file_path = ('data', 'devicelogs')
    root = os.path.dirname(__file__)

    def setUp(self):
        self.interface = FormProcessorInterface()

    def tearDown(self):
        DeviceReportEntry.objects.all().delete()
        UserEntry.objects.all().delete()

    @run_with_all_backends
    def test_basic_devicelog(self):
        xml = self.get_xml('devicelog')
        submit_form_locally(xml, 'test-domain')

        # Assert Device Report Entries
        self.assertEqual(DeviceReportEntry.objects.count(), 7)
        first = DeviceReportEntry.objects.first()

        self.assertEqual(first.type, 'resources')
        self.assertEqual(first.domain, 'test-domain')
        self.assertEqual(first.msg, 'Staging Sandbox: 54cfe6515fc24e3fafa1170b9a7c2a00')
        self.assertEqual(first.device_id, '351780060530179')
        self.assertEqual(
            first.app_version,
            'CommCare ODK, version "2.15.0"(335344). App v182. CommCare Version 2.15. Build 335344, built on: October-02-2014'
        )
        self.assertEqual(first.i, 0)
        self.assertIsNotNone(first.server_date)
        self.assertIsNotNone(first.date)

        second = DeviceReportEntry.objects.all()[1]
        self.assertEqual(second.type, 'user')
        self.assertEqual(second.username, 'ricatla')
        self.assertEqual(second.user_id, '428d454aa9abc74e1964e16d3565d6b6')

        # Assert UserEntries
        self.assertEqual(UserEntry.objects.count(), 1)
        first = UserEntry.objects.first()

        self.assertIsNotNone(first.xform_id)
        self.assertEqual(first.i, 0)
        self.assertEqual(first.user_id, '428d454aa9abc74e1964e16d3565d6b6')
        self.assertEqual(first.username, 'ricatla')
        self.assertEqual(first.sync_token, '848609ceef09fa567e98ca61e3b0514d')
