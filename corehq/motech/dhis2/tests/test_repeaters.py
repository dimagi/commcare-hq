from couchdbkit import BadValueError
from django.test import SimpleTestCase

from corehq.motech.dhis2.repeaters import is_dhis2_version


class IsDhis2VersionTests(SimpleTestCase):

    def test_major_version(self):
        self.assertTrue(is_dhis2_version('2.34'))

    def test_minor_version(self):
        self.assertTrue(is_dhis2_version('2.34.5'))

    def test_2(self):
        with self.assertRaises(BadValueError):
            is_dhis2_version('2')

    def test_api_version(self):
        with self.assertRaises(BadValueError):
            is_dhis2_version('34')

    def test_nan(self):
        with self.assertRaises(BadValueError):
            is_dhis2_version('not a number')
