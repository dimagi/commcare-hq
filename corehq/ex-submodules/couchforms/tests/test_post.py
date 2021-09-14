import json
import os

from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.util.json import CommCareJSONEncoder
from corehq.util.test_utils import TestFileMixin


@sharded
class PostTest(TestCase, TestFileMixin):
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)

    maxDiff = None

    def _process_sql_json(self, expected, xform_json, any_id_ok):
        expected['received_on'] = xform_json['received_on']
        expected['server_modified_on'] = xform_json['server_modified_on']
        if any_id_ok:
            expected['_id'] = xform_json['_id']
        return expected, xform_json

    def _test(self, name, any_id_ok=False):
        instance = self.get_xml(name)
        expected = self.get_json(name + '-sql')

        xform = submit_form_locally(instance, 'test-domain').xform
        xform_json = json.loads(json.dumps(xform.to_json(), cls=CommCareJSONEncoder))

        expected, xform_json = self._process_sql_json(expected, xform_json, any_id_ok)

        self.assertDictEqual(xform_json, expected)

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
