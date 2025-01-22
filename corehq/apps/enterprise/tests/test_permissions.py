from unittest import mock

from django.test.testcases import TestCase
from django.urls import reverse
from django.utils.http import urlencode

from .utils import create_enterprise_permissions
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.apps.fixtures.resources.v0_1 import InternalFixtureResource
from corehq.apps.users.models import (
    HQApiKey,
    HqPermissions,
    UserRole,
    WebUser,
)
from corehq.util.test_utils import flag_enabled


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
        cls.master_role = UserRole.create("state", "role1", permissions=HqPermissions(
            access_api=True,
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

    def test_get_by_domain(self):
        # Any domain in the account can be used to get the config
        configs = [
            EnterprisePermissions.get_by_domain('state'),
            EnterprisePermissions.get_by_domain('county'),
            EnterprisePermissions.get_by_domain('staging'),
        ]
        for config in configs:
            self.assertTrue(config.is_enabled)
            self.assertEqual(config.source_domain, 'state')
            self.assertListEqual(config.domains, ['county'])

        empty_config = EnterprisePermissions.get_by_domain('not-a-domain')
        self.assertFalse(empty_config.is_enabled)

    def test_get_source_domain(self):
        self.assertEqual(EnterprisePermissions.get_source_domain('state'), None)
        self.assertEqual(EnterprisePermissions.get_source_domain('county'), 'state')
        self.assertEqual(EnterprisePermissions.get_source_domain('staging'), None)

    def test_get_domains(self):
        self.assertListEqual(EnterprisePermissions.get_domains('state'), ['county'])
        self.assertListEqual(EnterprisePermissions.get_domains('county'), [])
        self.assertListEqual(EnterprisePermissions.get_domains('staging'), [])

    def test_is_source_domain(self):
        self.assertTrue(EnterprisePermissions.is_source_domain('state'))
        self.assertFalse(EnterprisePermissions.is_source_domain('county'))
        self.assertFalse(EnterprisePermissions.is_source_domain('staging'))

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

    @flag_enabled('API_THROTTLE_WHITELIST')
    def test_api_call(self):
        url = reverse('api_dispatch_list', kwargs={
            'domain': 'county',
            'api_name': 'v0.5',
            'resource_name': InternalFixtureResource._meta.resource_name,
        })
        username = self.web_user_non_admin.username
        api_params = urlencode({'username': username, 'api_key': self.api_key.plaintext_key})
        response = self.client.get(f"{url}?{api_params}")
        self.assertEqual(response.status_code, 200)
