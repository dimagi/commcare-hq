import unittest
from corehq.apps.receiverwrapper.util import get_commcare_version_from_appversion_text


class TestGetCommcareVersionFromAppversionText(unittest.TestCase):

    def test_full_version(self):
        appversion_text = ('CommCare ODK, version "2.11.0"(29272). App v65. CommCare Version 2.11.'
                          'Build 29272, built on: February-14-2014')
        self.assertEqual(get_commcare_version_from_appversion_text(appversion_text), '2.11.0')

    def test_missing_patch_version(self):
        appversion_text = ('CommCare Android, version "2.56"(1). App v16. CommCare Version 2.56.0.'
                          'Build 1, built on: 2025-03-05')
        self.assertEqual(get_commcare_version_from_appversion_text(appversion_text), '2.56.0')

    def test_different_language(self):
        appversion_text = u'संस्करण "2.27.8" (414593)'
        self.assertEqual(get_commcare_version_from_appversion_text(appversion_text), '2.27.8')

    def test_empty_string(self):
        appversion_text = ''
        self.assertIsNone(get_commcare_version_from_appversion_text(appversion_text))

    def test_only_major_version(self):
        appversion_text = 'CommCare Android, version "3"(12345).'
        self.assertEqual(get_commcare_version_from_appversion_text(appversion_text), '3.0.0')
