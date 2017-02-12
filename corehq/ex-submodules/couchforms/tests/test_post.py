import json
from django.test import TestCase
from django.conf import settings
import os
from corehq.apps.tzmigration.api import phone_timezones_should_be_processed
from corehq.apps.tzmigration.test_utils import \
    run_pre_and_post_timezone_migration

from corehq.util.test_utils import TestFileMixin
from corehq.form_processor.tests.utils import FormProcessorTestUtils, conditionally_run_with_all_backends, post_xform


class PostTest(TestCase, TestFileMixin):
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)

    maxDiff = None

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        super(PostTest, self).tearDown()

    def _process_sql_json(self, expected, xform_json, any_id_ok):
        expected['received_on'] = xform_json['received_on']
        if any_id_ok:
            expected['_id'] = xform_json['_id']
        return expected, xform_json

    def _process_couch_json(self, expected, xform_json, any_id_ok):
        expected['received_on'] = xform_json['received_on']
        expected['_rev'] = xform_json['_rev']
        for key in ['_attachments', 'external_blobs']:
            expected.pop(key, None)
            xform_json.pop(key, None)
        if any_id_ok:
            expected['_id'] = xform_json['_id']
        return expected, xform_json

    def _get_expected_name(self, name, tz_differs):
        expected_name = name
        if tz_differs and phone_timezones_should_be_processed():
            expected_name = name + '-tz'

        if getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            expected_name += '-sql'
        return expected_name

    def _test(self, name, any_id_ok=False, tz_differs=False):
        instance = self.get_xml(name)
        expected = self.get_json(self._get_expected_name(name, tz_differs))

        xform = post_xform(instance)
        xform_json = json.loads(json.dumps(xform.to_json()))

        if getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            expected, xform_json = self._process_sql_json(expected, xform_json, any_id_ok)
        else:
            expected, xform_json = self._process_couch_json(expected, xform_json, any_id_ok)

        self.assertDictEqual(xform_json, expected)

    @run_pre_and_post_timezone_migration
    def test_cloudant_template(self):
        self._test('cloudant-template', tz_differs=True)
        FormProcessorTestUtils.delete_all_xforms()

    @conditionally_run_with_all_backends
    def test_decimalmeta(self):
        self._test('decimalmeta', any_id_ok=True)

    @conditionally_run_with_all_backends
    def test_duplicate(self):
        self._test('duplicate')

    @conditionally_run_with_all_backends
    def test_meta(self):
        self._test('meta', any_id_ok=True)

    @conditionally_run_with_all_backends
    def test_meta_bad_username(self):
        self._test('meta_bad_username')

    @conditionally_run_with_all_backends
    def test_meta_dict_appversion(self):
        self._test('meta_dict_appversion')

    @conditionally_run_with_all_backends
    def test_namespaces(self):
        self._test('namespaces', any_id_ok=True)

    @conditionally_run_with_all_backends
    def test_unicode(self):
        self._test('unicode', any_id_ok=True)
