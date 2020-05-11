from django.test.testcases import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


@flag_enabled('ENTERPRISE_LINKED_DOMAINS')
class EnterpriseLinkedDomainTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.master_domain = 'domain'
        create_domain(cls.master_domain)
        cls.linked_domain = 'domain-2'
        create_domain(cls.linked_domain)
        cls.domain_link = DomainLink.link_domains(cls.linked_domain, cls.master_domain)
        cls.web_user_admin = WebUser.create(cls.master_domain, 'emma', 'badpassword', 'e@aol.com', is_admin=True)
        cls.web_user_non_admin = WebUser.create(cls.master_domain, 'clementine', 'worsepassword', 'c@aol.com')

    @classmethod
    def tearDownClass(cls):
        cls.domain_link.delete()
        cls.web_user_admin.delete()
        cls.web_user_non_admin.delete()
        Domain.get_by_name(cls.master_domain).delete()
        Domain.get_by_name(cls.linked_domain).delete()
        super().tearDownClass()

    def test_is_domain_admin(self):
        self.assertTrue(self.web_user_admin.is_domain_admin(self.master_domain))
        self.assertTrue(self.web_user_admin.is_domain_admin(self.linked_domain))
        self.assertFalse(self.web_user_non_admin.is_domain_admin(self.master_domain))
        self.assertFalse(self.web_user_non_admin.is_domain_admin(self.linked_domain))
