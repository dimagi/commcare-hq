from django.test import TestCase
from django.db import IntegrityError

from corehq.project_limits.exceptions import SystemLimitIllegalScopeChange
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

    def test_raises_error_if_changing_scope_from_global_to_domain(self):
        global_limit = SystemLimit.objects.create(key="general_limit", limit=10)
        with self.assertRaises(SystemLimitIllegalScopeChange):
            global_limit.domain = 'new-domain'  # this is changing scope from global to domain
            global_limit.save()

    def test_no_error_is_raised_if_changing_scope_from_domain_to_global(self):
        new_limit = SystemLimit.objects.create(key="domain_limit", limit=5, domain='test')
        new_limit.domain = ''
        # should not fail
        new_limit.save()

    def test_raises_db_error_if_conflicting_global_scopes(self):
        SystemLimit.objects.create(key="general_limit", limit=10)
        domain_limit = SystemLimit.objects.create(key="general_limit", limit=5, domain='test')
        with self.assertRaises(IntegrityError):
            domain_limit.domain = ''
            domain_limit.save()
