from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os

from django.conf import settings
from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.tzmigration.api import phone_timezones_should_be_processed
from corehq.apps.tzmigration.test_utils import \
    run_pre_and_post_timezone_migration
from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.util.json import CommCareJSONEncoder
from corehq.util.test_utils import TestFileMixin, softer_assert


class PostTestMixin(TestFileMixin):
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)

    maxDiff = None

    def _process_sql_json(self, expected, xform_json, any_id_ok):
        expected['received_on'] = xform_json['received_on']
        expected['server_modified_on'] = xform_json['server_modified_on']
        if any_id_ok:
            expected['_id'] = xform_json['_id']
        return expected, xform_json

    def _process_couch_json(self, expected, xform_json, any_id_ok):
        expected['received_on'] = xform_json['received_on']
        expected['server_modified_on'] = xform_json['server_modified_on']
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

        xform = submit_form_locally(instance, 'test-domain').xform
        xform_json = json.loads(json.dumps(xform.to_json(), cls=CommCareJSONEncoder))

        if getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            expected, xform_json = self._process_sql_json(expected, xform_json, any_id_ok)
        else:
            expected, xform_json = self._process_couch_json(expected, xform_json, any_id_ok)

        self.assertDictEqual(xform_json, expected)


class PostCouchOnlyTest(TestCase, PostTestMixin):

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        super(PostCouchOnlyTest, self).tearDown()

    @softer_assert()
    @run_pre_and_post_timezone_migration
    def test_cloudant_template(self):
        self._test('cloudant-template', tz_differs=True)
        FormProcessorTestUtils.delete_all_xforms()


class PostTest(TestCase, PostTestMixin):
    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        super(PostTest, self).tearDown()

    def test_decimalmeta(self):
        self._test('decimalmeta', any_id_ok=True)

    def test_duplicate(self):
        self._test('duplicate')

    def test_meta(self):
        self._test('meta', any_id_ok=True)

    def test_meta_bad_username(self):
        self._test('meta_bad_username')

    def test_meta_dict_appversion(self):
        self._test('meta_dict_appversion')

    def test_namespaces(self):
        self._test('namespaces', any_id_ok=True)

    def test_unicode(self):
        self._test('unicode', any_id_ok=True)


@use_sql_backend
class PostTestSQL(PostTest):
    pass
