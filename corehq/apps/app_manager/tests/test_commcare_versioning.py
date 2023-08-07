from looseversion import LooseVersion
from django.test import SimpleTestCase

from corehq.apps.app_manager.ui_translations.commcare_versioning import (
    get_strict_commcare_version_string,
)


class TestGetStrictCommcareVersionNumber(SimpleTestCase):

    def test_invalid_version_string(self):
        self.assertEqual(get_strict_commcare_version_string('2.0.1+'), None)

    def test_major_version_with_bugfix_string(self):
        self.assertEqual(get_strict_commcare_version_string('2.0.1'), '2.0.1')

    def test_major_version_string(self):
        self.assertEqual(get_strict_commcare_version_string('2.0.0'), '2.0')

    def test_major_version_with_minor_version_string(self):
        self.assertEqual(get_strict_commcare_version_string('2.23.0'), '2.23')

    def test_invalid_version_looseversion(self):
        self.assertEqual(
            get_strict_commcare_version_string(LooseVersion('2.0.1+')),
            None,
        )

    def test_major_version_with_bugfix_looseversion(self):
        self.assertEqual(
            get_strict_commcare_version_string(LooseVersion('2.0.1')),
            '2.0.1',
        )

    def test_major_version_looseversion(self):
        self.assertEqual(
            get_strict_commcare_version_string(LooseVersion('2.0.0')),
            '2.0',
        )

    def test_major_version_with_minor_version_looseversion(self):
        self.assertEqual(
            get_strict_commcare_version_string(LooseVersion('2.23.0')),
            '2.23',
        )
