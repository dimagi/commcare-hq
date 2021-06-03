from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.dbaccessors import get_available_domains_to_link
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.users.models import WebUser


class TestGetAvailableDomainsToLink(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestGetAvailableDomainsToLink, cls).setUpClass()

        cls.test_domain_obj1 = create_domain('test1')
        cls.test_domain_obj2 = create_domain('test2')
        cls.upstream_domain_obj = create_domain('upstream')
        cls.downstream_domain_obj = create_domain('downstream')

        cls.user = WebUser.create(
            domain=cls.test_domain_obj1.name,
            username='test@test.com',
            password='***',
            created_by=None,
            created_via=None,
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by=None)
        cls.test_domain_obj1.delete()
        cls.test_domain_obj2.delete()
        cls.upstream_domain_obj.delete()
        cls.downstream_domain_obj.delete()
        super(TestGetAvailableDomainsToLink, cls).tearDownClass()

    def test_no_available_domains_when_only_member_of_one(self):
        # already a member of this domain
        available_domains = get_available_domains_to_link(self.test_domain_obj1.name, self.user)
        self.assertEqual(0, len(available_domains))

    def test_available_domain_exists_given_member_of_two_fresh_domains(self):
        self.user.add_domain_membership(self.test_domain_obj2.name)
        self.user.save()
        self.addCleanup(self.user.delete_domain_membership, domain=self.test_domain_obj2.name)

        available_domains = get_available_domains_to_link(self.test_domain_obj1.name, self.user)
        self.assertEqual(1, len(available_domains))
        self.assertEqual(self.test_domain_obj2.name, available_domains[0])

    def test_no_available_domain_when_already_linked(self):
        self.user.add_domain_membership(self.upstream_domain_obj.name)
        self.addCleanup(self.user.delete_domain_membership, domain=self.upstream_domain_obj.name)

        self.user.add_domain_membership(self.downstream_domain_obj.name)
        self.addCleanup(self.user.delete_domain_membership, domain=self.downstream_domain_obj.name)
        self.user.save()

        link = DomainLink.link_domains('downstream', 'upstream')
        self.addCleanup(link.delete)

        available_domains = get_available_domains_to_link(self.test_domain_obj1.name, self.user)
        self.assertEqual(0, len(available_domains))
