from collections import namedtuple
import os
from django.test import SimpleTestCase
from corehq.apps.fixtures.exceptions import FixtureUploadError
from corehq.apps.fixtures.upload import FixtureWorkbook


def make_path(args):
    return os.path.join(os.path.dirname(__file__), *args)


class UploadTestConfig(namedtuple('UploadTestConfig', ['upload_file_', 'error_messages'])):
    @property
    def upload_file(self):
        return make_path(self.upload_file_.split('/'))


multiple_errors_test = UploadTestConfig('test_upload/incorrect_fixtures.xlsx', [
    u"Excel-sheet 'level_1' does not contain the column 'fun_fact' as specified in its 'types' definition",
    u"Excel-sheet 'level_1' does not contain the column 'other' as specified in its 'types' definition",
    u"Excel-sheet 'level_2' does not contain the column 'other' as specified in its 'types' definition",
    u"There's no sheet for type 'level_3' in 'types' sheet. There must be one sheet per row in the 'types' sheet.",
])


class TestFixtureUpload(SimpleTestCase):
    maxDiff = None

    def _test(self, config):
        wb = FixtureWorkbook(config.upload_file)
        with self.assertRaises(FixtureUploadError) as context:
            wb.validate()
        self.assertEqual(context.exception.errors, config.error_messages)

    def test_multiple_errors(self):
        self._test(multiple_errors_test)
