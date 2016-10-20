import os
from django.test import SimpleTestCase
from corehq.apps.fixtures.exceptions import FixtureUploadError
from corehq.apps.fixtures.upload import FixtureWorkbook

dot = os.path.dirname(__file__)

UPLOAD_FILE = os.path.join(dot, 'test_upload', 'incorrect_fixtures.xlsx')
ERRORS = [
    u"Excel-sheet 'level_1' does not contain the column 'fun_fact' as specified in its 'types' definition",
    u"Excel-sheet 'level_1' does not contain the column 'other' as specified in its 'types' definition",
    u"Excel-sheet 'level_2' does not contain the column 'other' as specified in its 'types' definition",
    u"There's no sheet for type 'level_3' in 'types' sheet. There must be one sheet per row in the 'types' sheet.",
]


class TestFixtureUpload(SimpleTestCase):
    maxDiff = None

    def test(self):
        wb = FixtureWorkbook(UPLOAD_FILE)
        with self.assertRaises(FixtureUploadError) as context:
            wb.validate()
        self.assertEqual(context.exception.errors, ERRORS)
