import os
from django.test import SimpleTestCase, TestCase

from corehq.apps.receiverwrapper import submit_form_locally
from corehq.util.test_utils import TestFileMixin
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils import convert_xform_to_json
from phonelog.models import UserEntry, DeviceReportEntry, UserErrorEntry
from phonelog.utils import _get_logs


class DeviceLogTest(TestCase, TestFileMixin):
    file_path = ('data', 'devicelogs')
    root = os.path.dirname(__file__)

    def setUp(self):
        self.interface = FormProcessorInterface()

    def tearDown(self):
        DeviceReportEntry.objects.all().delete()
        UserEntry.objects.all().delete()
        UserErrorEntry.objects.all().delete()

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

        # Assert UserErrorEntries
        self.assertEqual(UserErrorEntry.objects.count(), 2)
        user_error = UserErrorEntry.objects.all()[1]
        self.assertEqual(user_error.type, 'error-config')
        self.assertEqual(user_error.user_id, '428d454aa9abc74e1964e16d3565d6b6')
        self.assertEqual(user_error.version_number, 604)
        self.assertEqual(user_error.app_id, '36c0bdd028d14a52cbff95bb1bfd0962')
        self.assertEqual(user_error.expr, '/data/fake')

    @run_with_all_backends
    def test_subreports_that_shouldnt_fail(self):
        xml = self.get_xml('subreports_that_shouldnt_fail')
        submit_form_locally(xml, 'test-domain')


class TestDeviceLogUtils(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'devicelogs')
    root = os.path.dirname(__file__)

    def test_single_node(self):
        form_data = convert_xform_to_json(self.get_xml('single_node'))
        self.assertEqual(
            _get_logs(form_data, 'log_subreport', 'log'),
            [{u'@date': u'2016-03-20T20:46:08.664+05:30',
              u'msg': u'Logging out service login',
              u'type': u'maintenance'},
             {u'@date': u'2016-03-20T20:46:08.988+05:30',
              u'msg': u'login|user.test|gxpg40k9lh9w7853w3gc91o1g7zu1wi8',
              u'type': u'user'}]
        )

    def test_multiple_nodes(self):
        form_data = convert_xform_to_json(self.get_xml('multiple_nodes'))
        self.assertEqual(
            _get_logs(form_data, 'log_subreport', 'log'),
            [{u'@date': u'2016-03-20T20:46:08.664+05:30',
              u'msg': u'Logging out service login',
              u'type': u'maintenance'},
             {u'@date': u'2016-03-20T20:46:08.988+05:30',
              u'msg': u'login|user.test|gxpg40k9lh9w7853w3gc91o1g7zu1wi8',
              u'type': u'user'},
             {u'@date': u'2016-03-19T23:50:11.219+05:30',
              u'msg': u'Staging Sandbox: 7t3iyx01dxnn49a5xqt32916q5u7epn0',
              u'type': u'resources'}]
        )
