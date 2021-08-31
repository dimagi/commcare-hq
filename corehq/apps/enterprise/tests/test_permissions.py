import mock

from django.test.testcases import TestCase
from django.urls import reverse
from django.utils.http import urlencode

from .utils import create_enterprise_permissions
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.fixtures.resources.v0_1 import InternalFixtureResource
from corehq.apps.users.models import (
    HQApiKey,
    Permissions,
    UserRole,
    WebUser,
)


class EnterprisePermissionsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up domains
        cls.domain = 'state'
        create_domain(cls.domain)
        create_domain('county')
        create_domain('staging')

        # Set up users
        cls.master_role = UserRole.create("state", "role1", permissions=Permissions(
            view_web_users=True,
            edit_web_users=False,
            view_groups=True,
            edit_groups=False,
            edit_apps=True,  # needed for InternalFixtureResource
            view_apps=True,
        ))
        cls.web_user_admin = WebUser.create('state', 'emma', 'badpassword', None, None, email='e@aol.com',
                                            is_admin=True)
        cls.web_user_non_admin = WebUser.create('state', 'clementine', 'worsepassword', None, None,
                                                email='c@aol.com')
        cls.web_user_non_admin.set_role('state', cls.master_role.get_qualified_id())
        cls.web_user_non_admin.save()
        cls.api_key, _ = HQApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.web_user_non_admin))

        # Set up permissions
        create_enterprise_permissions(cls.web_user_admin.username, 'state', ['county'], ['staging'])

    def setUp(self):
        patches = [
            mock.patch.object(WebUser, 'has_permission', WebUser.has_permission.__wrapped__),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    @classmethod
    def tearDownClass(cls):
        cls.web_user_admin.delete(cls.domain, deleted_by=None)
        cls.web_user_non_admin.delete(cls.domain, deleted_by=None)
        cls.api_key.delete()
        cls.master_role.delete()
        Domain.get_by_name('county').delete()
        Domain.get_by_name('state').delete()
        Domain.get_by_name('staging').delete()
        super().tearDownClass()

    def test_permission_mirroring(self):
        for domain in ('state', 'county'):
            self.assertTrue(self.web_user_admin.is_domain_admin(domain))
            self.assertFalse(self.web_user_non_admin.is_domain_admin(domain))

            # Non-admin's permissions should match self._master_role
            self.assertTrue(self.web_user_non_admin.has_permission(domain, "view_groups"))
            self.assertFalse(self.web_user_non_admin.has_permission(domain, "edit_groups"))

            # Admin's has no role but `is_admin` gives them access to everything
            self.assertTrue(self.web_user_admin.has_permission(domain, "view_groups"))
            self.assertTrue(self.web_user_admin.has_permission(domain, "edit_groups"))

        # No one gets any permissions in ignored domain
        domain = 'staging'
        self.assertFalse(self.web_user_non_admin.has_permission(domain, "view_groups"))
        self.assertFalse(self.web_user_non_admin.has_permission(domain, "edit_groups"))
        self.assertFalse(self.web_user_admin.has_permission(domain, "view_groups"))
        self.assertFalse(self.web_user_admin.has_permission(domain, "edit_groups"))

    def test_api_call(self):
        url = reverse('api_dispatch_list', kwargs={
            'domain': 'county',
            'api_name': 'v0.5',
            'resource_name': InternalFixtureResource._meta.resource_name,
        })
        username = self.web_user_non_admin.username
        api_params = urlencode({'username': username, 'api_key': self.api_key.key})
        response = self.client.get(f"{url}?{api_params}")
        self.assertEqual(response.status_code, 200)
