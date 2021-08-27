from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.models import DomainLink


class DomainLinkUrlsTest(TestCase):

    domain = 'domain-link-tests'

    @classmethod
    def setUpClass(cls):
        super(DomainLinkUrlsTest, cls).setUpClass()
        cls.downstream = create_domain('downstream-domain')
        cls.upstream = create_domain('upstream-domain')

    @classmethod
    def tearDownClass(cls):
        super(DomainLinkUrlsTest, cls).tearDownClass()
        cls.downstream.delete()
        cls.upstream.delete()

    def test_upstream_url(self):
        domain_link = DomainLink.link_domains(linked_domain=self.downstream.name, master_domain=self.upstream.name)
        self.addCleanup(domain_link.delete)

        expected_upstream_url = '/a/upstream-domain/settings/project/domain_links/'
        self.assertEqual(expected_upstream_url, domain_link.upstream_url)

    def test_remote_upstream_url(self):
        domain_link = DomainLink.link_domains(linked_domain=self.downstream.name, master_domain=self.upstream.name)
        domain_link.remote_base_url = 'test.base.url'
        domain_link.save()
        self.addCleanup(domain_link.delete)

        expected_upstream_url = 'test.base.url/a/upstream-domain/'
        self.assertEqual(expected_upstream_url, domain_link.upstream_url)

    def test_downstream_url(self):
        domain_link = DomainLink.link_domains(linked_domain=self.downstream.name, master_domain=self.upstream.name)
        self.addCleanup(domain_link.delete)

        expected_downstream_url = '/a/downstream-domain/settings/project/domain_links/'
        self.assertEqual(expected_downstream_url, domain_link.downstream_url)

    def test_remote_downstream_url(self):
        domain_link = DomainLink.link_domains(linked_domain=self.downstream.name, master_domain=self.upstream.name)
        domain_link.remote_base_url = 'test.base.url'
        domain_link.save()
        self.addCleanup(domain_link.delete)

        expected_downstream_url = self.downstream.name  # remote downstream urls are equal to the name
        self.assertEqual(expected_downstream_url, domain_link.downstream_url)
