import os
from django.test import SimpleTestCase, TestCase

from corehq.apps.receiverwrapper import submit_form_locally
from corehq.util.test_utils import TestFileMixin
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils import convert_xform_to_json
from phonelog.models import UserEntry, DeviceReportEntry, UserErrorEntry, ForceCloseEntry
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
        ForceCloseEntry.objects.all().delete()

    def assert_properties_equal(self, obj, expected):
        for prop, value in expected:
            actual = getattr(obj, prop)
            msg = ("{}.{} mismatch!\nexpected:\t'{}'\ngot:\t\t'{}'"
                   .format(obj.__class__.__name__, prop, value, actual))
            self.assertEqual(actual, value, msg)

    @run_with_all_backends
    def test_basic_devicelog(self):
        xml = self.get_xml('devicelog')
        submit_form_locally(xml, 'test-domain')
        self.assert_device_report_entries()
        self.assert_user_entries()
        self.assert_user_error_entries()
        self.assert_force_close_entries()

    def assert_device_report_entries(self):
        self.assertEqual(DeviceReportEntry.objects.count(), 7)
        first = DeviceReportEntry.objects.first()

        self.assert_properties_equal(first, (
            ('type', 'resources'),
            ('domain', 'test-domain'),
            ('msg', 'Staging Sandbox: 54cfe6515fc24e3fafa1170b9a7c2a00'),
            ('device_id', '351780060530179'),
            ('i', 0),
            ('app_version', 'CommCare ODK, version "2.15.0"(335344). App v182. '
                            'CommCare Version 2.15. Build 335344, built on: '
                            'October-02-2014')
        ))
        self.assertIsNotNone(first.server_date)
        self.assertIsNotNone(first.date)

        second = DeviceReportEntry.objects.all()[1]
        self.assert_properties_equal(second, (
            ('type', 'user'),
            ('username', 'ricatla'),
            ('user_id', '428d454aa9abc74e1964e16d3565d6b6'),
        ))

    def assert_user_entries(self):
        self.assertEqual(UserEntry.objects.count(), 1)
        user_entry = UserEntry.objects.first()

        self.assertIsNotNone(user_entry.xform_id)
        self.assert_properties_equal(user_entry, (
            ('i', 0),
            ('user_id', '428d454aa9abc74e1964e16d3565d6b6'),
            ('username', 'ricatla'),
            ('sync_token', '848609ceef09fa567e98ca61e3b0514d'),
        ))

    def assert_user_error_entries(self):
        self.assertEqual(UserErrorEntry.objects.count(), 2)
        user_error = UserErrorEntry.objects.all()[1]
        self.assert_properties_equal(user_error, (
            ('type', 'error-config'),
            ('user_id', '428d454aa9abc74e1964e16d3565d6b6'),
            ('version_number', 604),
            ('app_id', '36c0bdd028d14a52cbff95bb1bfd0962'),
            ('expr', '/data/fake'),
            ('context_node', '/data/foo'),
        ))

    def assert_force_close_entries(self):
        self.assertEqual(ForceCloseEntry.objects.count(), 1)
        force_closure = ForceCloseEntry.objects.first()

        self.assert_properties_equal(force_closure, (
            ('domain', 'test-domain'),
            ('app_id', '36c0bdd028d14a52cbff95bb1bfd0962'),
            ('version_number', 15),
            ('user_id', 'ahelis3q3s0c33ms8r5is7yrei7t02m8'),
            ('type', 'forceclose'),
            ('android_version', '6.0.1'),
            ('device_model', 'Nexus 5X'),
            ('session_readable', ''),
            ('session_serialized', 'AAAAAA=='),
        ))
        self.assertEqual(force_closure.date.isoformat(), '2016-03-15T07:52:04.573000')
        self.assertIsNotNone(force_closure.xform_id)
        self.assertIsNotNone(force_closure.server_date)
        self.assertIn("java.lang.Exception: exception_text", force_closure.msg)

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

    def test_single_entry(self):
        form_data = convert_xform_to_json(self.get_xml('single_entry'))
        self.assertEqual(
            _get_logs(form_data, 'user_error_subreport', 'user_error'),
            [{"session": "frame: (COMMAND_ID m1)",
              "user_id": "65t2l8ga654k93z92j236e2h30jt048b",
              "expr": "",
              "app_id": "skj94l95tw0k6v8esdj9s2g4chfpup83",
              "version": "89",
              "msg": ("XPath evaluation: type mismatch It looks like this "
                      "question contains a reference to path number which "
                      "evaluated to instance(item-list:numbers)/numbers_list"
                      "/numbers[1]/number which was not found. This often "
                      "means you forgot to include the full path to the "
                      "question -- e.g. /data/[node]"),
              "@date": "2016-03-23T12:27:33.681-04",
              "type": "error-config"}]
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
