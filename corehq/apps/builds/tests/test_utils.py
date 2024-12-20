from django.test import SimpleTestCase
from corehq.apps.builds.utils import is_out_of_date


class TestVersionUtils(SimpleTestCase):

    def test_is_out_of_date(self):
        test_cases = [
            # (version_in_use, latest_version, expected_result)
            ('2.53.0', '2.53.1', True),     # Normal case - out of date
            ('2.53.1', '2.53.1', False),    # Same version - not out of date
            ('2.53.2', '2.53.1', False),    # Higher version - not out of date
            (None, '2.53.1', False),        # None version_in_use
            ('2.53.1', None, False),        # None latest_version
            ('invalid', '2.53.1', False),   # Invalid version string
            ('2.53.1', 'invalid', False),   # Invalid latest version
            ('6', '7', True),               # Normal case - app version is integer
            (None, None, False),            # None version_in_use and latest_version
            ('2.54', '2.54.0', False),      # Edge case - should not be out of date
            ('2.54.0', '2.54', False),       # Edge case - should not be out of date
        ]

        for version_in_use, latest_version, expected in test_cases:
            with self.subTest(version_in_use=version_in_use, latest_version=latest_version):
                result = is_out_of_date(version_in_use, latest_version)
                self.assertEqual(
                    result,
                    expected,
                    f"Expected is_out_of_date('{version_in_use}', '{latest_version}') to be {expected}"
                )
