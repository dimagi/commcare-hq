from django.test import SimpleTestCase

from corehq.motech.dhis2.version import Version


class TestVersion(SimpleTestCase):

    def test_coerce_major_minor_patch(self):
        version = Version.coerce("12.34.56")
        self.assertEqual(version.major, 12)
        self.assertEqual(version.minor, 34)
        self.assertEqual(version.patch, 56)

    def test_coerce_major_minor(self):
        version = Version.coerce("12.34")
        self.assertEqual(version.major, 12)
        self.assertEqual(version.minor, 34)
        self.assertEqual(version.patch, 0)

    def test_coerce_major(self):
        version = Version.coerce("12")
        self.assertEqual(version.major, 12)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)

    def test_coerce_blank(self):
        with self.assertRaises(ValueError):
            Version.coerce("")

    def test_coerce_none(self):
        with self.assertRaises(ValueError):
            Version.coerce(None)

    def test_coerce_non_numeric(self):
        version = Version.coerce("12.ab.56")
        self.assertEqual(version.major, 12)
        self.assertEqual(version.minor, 56)
        self.assertEqual(version.patch, 0)

    def test_str(self):
        version = Version("12.34.56")
        self.assertEqual(str(version), "12.34.56")

    def test_eq(self):
        self.assertTrue(Version("12.34.56") == Version("12.34.56"))

    def test_gt(self):
        self.assertTrue(Version("12.34.56") > Version("12.34.0"))
