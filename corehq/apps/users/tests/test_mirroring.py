import mock

from django.test.testcases import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import (
    DomainMembership,
    DomainPermissionsMirror,
    DomainPermissionsMirrorSource,
    Permissions,
    UserRole,
    WebUser,
)


class DomainPermissionsMirrorTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up domains
        cls.source = DomainPermissionsMirrorSource(name='state')
        cls.source.save()
        cls.mirror_domain_name = 'county'
        mirror = DomainPermissionsMirror(name=cls.mirror_domain_name, source=cls.source)
        mirror.save()
        create_domain(cls.source.name)
        create_domain(cls.mirror_domain_name)

        # Set up users
        cls.web_user_admin = WebUser.create(cls.source.name, 'emma', 'badpassword', 'e@aol.com', is_admin=True)
        cls.web_user_non_admin = WebUser.create(cls.source.name, 'clementine', 'worsepassword', 'c@aol.com')

    def setUp(self):
        patches = [
            mock.patch.object(DomainMembership, 'role', self._master_role()),
            mock.patch.object(WebUser, 'has_permission', WebUser.has_permission.__wrapped__),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    @classmethod
    def _master_role(cls):
        return UserRole(
            domain=cls.source.name,
            permissions=Permissions(
                view_web_users=True,
                edit_web_users=False,
                view_groups=True,
                edit_groups=False,
            )
        )

    @classmethod
    def tearDownClass(cls):
        cls.web_user_admin.delete()
        cls.web_user_non_admin.delete()
        Domain.get_by_name(cls.mirror_domain_name).delete()
        Domain.get_by_name(cls.source.name).delete()
        cls.source.delete()
        super().tearDownClass()

    def test_permission_mirroring(self):
        for domain in (self.source.name, self.mirror_domain_name):
            self.assertTrue(self.web_user_admin.is_domain_admin(domain))
            self.assertFalse(self.web_user_non_admin.is_domain_admin(domain))

            # Non-admin's permissions should match self._master_role
            self.assertTrue(self.web_user_non_admin.has_permission(domain, "view_groups"))
            self.assertFalse(self.web_user_non_admin.has_permission(domain, "edit_groups"))

            # Admin's role is also self._master_role because of the patch, but is_admin gets checked first
            self.assertTrue(self.web_user_admin.has_permission(domain, "view_groups"))
            self.assertTrue(self.web_user_admin.has_permission(domain, "edit_groups"))
