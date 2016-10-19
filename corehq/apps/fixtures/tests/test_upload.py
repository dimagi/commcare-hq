import os
from django.test import SimpleTestCase
from corehq.apps.fixtures.exceptions import FixtureUploadError
from corehq.apps.fixtures.upload import FixtureWorkbook

dot = os.path.dirname(__file__)


class TestFixtureUpload(SimpleTestCase):
    def test(self):
        wb = FixtureWorkbook(os.path.join(dot, 'test_upload', 'incorrect_fixtures.xlsx'))
        with self.assertRaises(FixtureUploadError):
            wb.validate()
