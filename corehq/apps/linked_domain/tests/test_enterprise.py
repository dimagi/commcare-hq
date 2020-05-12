import mock

from django.test.testcases import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.users.models import DomainMembership, Permissions, UserRole, WebUser
from corehq.util.test_utils import flag_enabled


@flag_enabled('ENTERPRISE_LINKED_DOMAINS')
class EnterpriseLinkedDomainTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up domains
        cls.master_domain = 'domain'
        create_domain(cls.master_domain)
        cls.linked_domain = 'domain-2'
        create_domain(cls.linked_domain)
        cls.domain_link = DomainLink.link_domains(cls.linked_domain, cls.master_domain)

        # Set up users
        cls.web_user_admin = WebUser.create(cls.master_domain, 'emma', 'badpassword', 'e@aol.com', is_admin=True)
        cls.web_user_non_admin = WebUser.create(cls.master_domain, 'clementine', 'worsepassword', 'c@aol.com')

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
            domain=cls.master_domain,
            permissions=Permissions(
                view_web_users=True,
                edit_web_users=False,
                view_groups=True,
                edit_groups=False,
            )
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain_link.delete()
        cls.web_user_admin.delete()
        cls.web_user_non_admin.delete()
        Domain.get_by_name(cls.master_domain).delete()
        Domain.get_by_name(cls.linked_domain).delete()
        super().tearDownClass()

    def test_is_domain_admin(self):
        for domain in (self.master_domain, self.linked_domain):
            self.assertTrue(self.web_user_admin.is_domain_admin(domain))
            self.assertFalse(self.web_user_non_admin.is_domain_admin(domain))

            # Non-admin's permissions should match self._master_role
            self.assertTrue(self.web_user_non_admin.has_permission(domain, "view_groups"))
            self.assertFalse(self.web_user_non_admin.has_permission(domain, "edit_groups"))

            # Admin's role is also self._master_role because of the patch, but is_admin gets checked first
            self.assertTrue(self.web_user_admin.has_permission(domain, "view_groups"))
            self.assertTrue(self.web_user_admin.has_permission(domain, "edit_groups"))
