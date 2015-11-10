import json
from django.test import TestCase
import os
from corehq.apps.tzmigration import phone_timezones_should_be_processed
from corehq.apps.tzmigration.test_utils import \
    run_pre_and_post_timezone_migration

from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.test_utils import FormProcessorTestUtils


class PostTest(TestCase):

    maxDiff = None

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()

    def _test(self, name, any_id_ok=False, tz_differs=False):
        with open(os.path.join(os.path.dirname(__file__), 'data', '{name}.xml'.format(name=name))) as f:
            instance = f.read()

        if tz_differs and phone_timezones_should_be_processed():
            expected_name = name + '-tz'
        else:
            expected_name = name

        with open(os.path.join(os.path.dirname(__file__), 'data',
                               '{name}.json'.format(name=expected_name))) as f:
            expected = json.load(f)

        xform = FormProcessorInterface().post_xform(instance)
        xform_json = json.loads(json.dumps(xform.to_json()))

        expected['received_on'] = xform_json['received_on']
        expected['_rev'] = xform_json['_rev']
        expected['_attachments'] = None
        xform_json['_attachments'] = None
        if any_id_ok:
            expected['_id'] = xform_json['_id']

        self.assertDictEqual(xform_json, expected)

    @run_pre_and_post_timezone_migration
    def test_cloudant_template(self):
        self._test('cloudant-template', tz_differs=True)
        FormProcessorTestUtils.delete_all_xforms()

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
