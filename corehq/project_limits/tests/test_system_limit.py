from django.test import TestCase

from corehq.project_limits.models import SystemLimit


class TestSystemLimitMethods(TestCase):

    def test_for_key_returns_none_if_no_limit_set(self):
        self.assertIsNone(SystemLimit.for_key("imaginary_limit"))

    def test_for_key_returns_zero_if_limit_set_to_zero(self):
        SystemLimit.objects.create(key="general_limit", limit=0)
        self.assertEqual(SystemLimit.for_key("general_limit"), 0)

    def test_for_key_returns_general_limit(self):
        SystemLimit.objects.create(key="general_limit", limit=10)  # domain defaults to blank
        self.assertEqual(SystemLimit.for_key("general_limit"), 10)
        self.assertEqual(SystemLimit.for_key("general_limit", domain="no_match"), 10)

    def test_for_key_returns_domain_specific_limit(self):
        SystemLimit.objects.create(key="general_limit", limit=10)
        SystemLimit.objects.create(key="general_limit", limit=20, domain="specific")
        self.assertEqual(SystemLimit.for_key("general_limit"), 10)
        self.assertEqual(SystemLimit.for_key("general_limit", domain="specific"), 20)

    def test_patching_cache_works(self):
        # if the logic in ../patch_cache.py fails, this test should catch that
        # since we are not clearing cache in between limit updates
        SystemLimit.objects.create(key="general_limit", limit=10)
        self.assertEqual(SystemLimit.for_key("general_limit"), 10)
        SystemLimit.objects.update_or_create(defaults={"limit": 11}, key="general_limit")
        self.assertEqual(SystemLimit.for_key("general_limit"), 11)
