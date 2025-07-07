from django.db import IntegrityError
from django.test import TestCase

from corehq.project_limits.exceptions import SystemLimitIllegalScopeChange
from corehq.project_limits.models import SystemLimit


class TestSystemLimitMethods(TestCase):

    def test_creates_limit_if_does_not_exist(self):
        self.assertFalse(SystemLimit.objects.filter(key="imaginary_limit", limit=10).exists())
        SystemLimit.get_limit_for_key("imaginary_limit", 10)
        self.assertTrue(SystemLimit.objects.filter(key="imaginary_limit", limit=10).exists())

    def test_only_one_limit_created(self):
        SystemLimit.get_limit_for_key("imaginary_limit", 10)
        SystemLimit.get_limit_for_key("imaginary_limit", 10)
        SystemLimit.get_limit_for_key("imaginary_limit", 10, domain="random")
        self.assertEqual(SystemLimit.objects.filter(key="imaginary_limit", limit=10).count(), 1)

    def test_existing_limit_is_not_updated_if_default_changes(self):
        SystemLimit.get_limit_for_key("imaginary_limit", 10)
        limit = SystemLimit.get_limit_for_key("imaginary_limit", 20)
        self.assertEqual(limit, 10)

    def test_global_limit_used_if_no_domain_limit_exists(self):
        SystemLimit.get_limit_for_key("general_limit", 10)
        self.assertEqual(SystemLimit.get_limit_for_key("general_limit", 10, domain="no_match"), 10)

    def test_domain_specific_limit(self):
        SystemLimit.objects.create(key="general_limit", limit=10)
        SystemLimit.objects.create(key="general_limit", limit=20, domain="specific")
        self.assertEqual(SystemLimit.get_limit_for_key("general_limit", 10), 10)
        self.assertEqual(SystemLimit.get_limit_for_key("general_limit", 10, domain="specific"), 20)

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
