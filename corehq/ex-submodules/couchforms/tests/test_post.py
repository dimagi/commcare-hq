import json
from django.test import TestCase
import os
from corehq.apps.tzmigration import phone_timezones_should_be_processed
from corehq.apps.tzmigration.test_utils import \
    run_pre_and_post_timezone_migration
from couchforms.models import XFormInstance
from couchforms.tests.testutils import create_and_save_xform


class PostTest(TestCase):

    maxDiff = None

    def _test(self, name, any_id_ok=False, tz_differs=False):
        with open(os.path.join(os.path.dirname(__file__), 'data', '{name}.xml'.format(name=name))) as f:
            instance = f.read()

        if tz_differs and phone_timezones_should_be_processed():
            expected_name = name + '-tz'
        else:
            expected_name = name

        with open(os.path.join(os.path.dirname(__file__), 'data',
                               '{name}.json'.format(name=expected_name))) as f:
            result = json.load(f)

        with create_and_save_xform(instance) as doc_id:
            xform = XFormInstance.get(doc_id)
            try:
                xform_json = xform.to_json()
                result['received_on'] = xform_json['received_on']
                result['_rev'] = xform_json['_rev']
                if any_id_ok:
                    result['_id'] = xform_json['_id']
                self.assertDictEqual(xform_json, result)
            except Exception:
                # to help when bootstrapping a new test case
                print json.dumps(xform_json)
                raise
            finally:
                xform.delete()

    @run_pre_and_post_timezone_migration
    def test_cloudant_template(self):
        self._test('cloudant-template', tz_differs=True)

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
