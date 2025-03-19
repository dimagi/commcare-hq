from django.test import TestCase

from corehq.apps.cleanup.utils import DeletedDomains, migrate_to_deleted_on
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.domain.shortcuts import create_domain


class TestDeletedDomains(TestCase):

    def test_is_domain_deleted_returns_true_for_deleted_domain(self):
        self.assertTrue(
            DeletedDomains().is_domain_deleted(self.deleted_domain.name))

    def test_is_domain_deleted_returns_false_for_active_domain(self):
        self.assertFalse(
            DeletedDomains().is_domain_deleted(self.active_domain.name))

    def test_is_domain_deleted_returns_false_for_inactive_domain(self):
        self.assertFalse(
            DeletedDomains().is_domain_deleted(self.inactive_domain.name))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('active', active=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.inactive_domain = create_domain('inactive', active=False)
        cls.addClassCleanup(cls.inactive_domain.delete)
        cls.deleted_domain = create_domain('deleted', active=False)
        cls.deleted_domain.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.deleted_domain.delete)


class TestMigrateToDeletedOn(TestCase):

    def test_deleted_on_is_set_if_object_is_deleted(self):
        rule = AutomaticUpdateRule.objects.create(domain='test', deleted=True)
        self.assertIsNone(rule.deleted_on)
        migrate_to_deleted_on(AutomaticUpdateRule, 'deleted', should_audit=True)
        self.assertIsNotNone(AutomaticUpdateRule.objects.get(id=rule.id).deleted_on)

    def test_deleted_on_is_not_set_if_object_is_not_deleted(self):
        rule = AutomaticUpdateRule.objects.create(domain='test')
        self.assertIsNone(rule.deleted_on)
        migrate_to_deleted_on(AutomaticUpdateRule, 'deleted', should_audit=True)
        self.assertIsNone(AutomaticUpdateRule.objects.get(id=rule.id).deleted_on)
