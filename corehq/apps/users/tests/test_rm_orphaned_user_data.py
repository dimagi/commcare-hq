from django.contrib.auth.models import User
from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.management.commands.rm_orphaned_user_data import remove_orphaned_user_data_for_domain
from corehq.apps.users.models import SQLUserData, WebUser


class TestOrphanedUserData(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-orphaned-user-data'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

    def test_unknown_user_data_is_removed(self):
        user = User.objects.create(username='test', password='abc123')
        SQLUserData.objects.create(django_user=user, user_id='abcdef', domain=self.domain, data={})

        remove_orphaned_user_data_for_domain(self.domain, dry_run=False)

        self.assertFalse(SQLUserData.objects.filter(django_user=user, domain=self.domain).exists())

    def test_active_user_data_is_not_removed(self):
        user = User.objects.create(username='test', password='abc123')
        web_user = WebUser.create(self.domain, 'testuser', 'abc123', None, None)
        self.addCleanup(web_user.delete, None, None)
        SQLUserData.objects.create(django_user=user, user_id=web_user._id, domain=self.domain, data={})

        remove_orphaned_user_data_for_domain(self.domain, dry_run=False)

        self.assertTrue(SQLUserData.objects.filter(django_user=user, domain=self.domain).exists())

    def test_orphaned_user_data_is_removed(self):
        user = User.objects.create(username='test', password='abc123')
        web_user = WebUser.create(self.domain, 'testuser', 'abc123', None, None)
        self.addCleanup(web_user.delete, None, None)
        SQLUserData.objects.create(django_user=user, user_id=web_user._id, domain=self.domain, data={})

        web_user.delete_domain_membership(self.domain)
        web_user.save()
        remove_orphaned_user_data_for_domain(self.domain, dry_run=False)

        self.assertFalse(SQLUserData.objects.filter(django_user=user, domain=self.domain).exists())

    def test_dry_run_works(self):
        user = User.objects.create(username='test', password='abc123')
        web_user = WebUser.create(self.domain, 'testuser', 'abc123', None, None)
        self.addCleanup(web_user.delete, None, None)
        SQLUserData.objects.create(django_user=user, user_id=web_user._id, domain=self.domain, data={})

        web_user.delete_domain_membership(self.domain)
        web_user.save()
        remove_orphaned_user_data_for_domain(self.domain, dry_run=True)

        self.assertTrue(SQLUserData.objects.filter(django_user=user, domain=self.domain).exists())
