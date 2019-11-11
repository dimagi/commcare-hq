from django.test import SimpleTestCase

from couchdbkit import BadValueError

from corehq.motech.dhis2.repeaters import (
    Dhis2Repeater,
    is_dhis2_version,
    is_dhis2_version_or_blank,
)


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

    def test_none(self):
        with self.assertRaises(BadValueError):
            is_dhis2_version(None)

    def test_blank(self):
        with self.assertRaises(BadValueError):
            is_dhis2_version("")


class IsDhis2VersionOrBlankTests(SimpleTestCase):

    def test_none(self):
        self.assertTrue(is_dhis2_version_or_blank(None))

    def test_blank(self):
        self.assertTrue(is_dhis2_version_or_blank(""))


class ApiVersionTests(SimpleTestCase):

    def test_2_xy_z(self):
        repeater = Dhis2Repeater.wrap({"dhis2_version": "2.34.5"})
        self.assertEqual(repeater.api_version, "34")

    def test_2_xy(self):
        repeater = Dhis2Repeater.wrap({"dhis2_version": "2.34"})
        self.assertEqual(repeater.api_version, "34")

    def test_none(self):
        repeater = Dhis2Repeater.wrap({"dhis2_version": None})
        self.assertIsNone(repeater.api_version)

    def test_blank(self):
        repeater = Dhis2Repeater.wrap({"dhis2_version": ""})
        self.assertIsNone(repeater.api_version)
