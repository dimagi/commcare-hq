from django.http import Http404
from django.test import TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.applications import link_app_in_existing_domain_link
from corehq.apps.linked_domain.models import DomainLink


class CreateLinkedAppTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(CreateLinkedAppTest, cls).setUpClass()
        cls.upstream_domain_obj = create_domain('upstream-domain')
        cls.upstream_domain = cls.upstream_domain_obj.name
        cls.downstream_domain_obj = create_domain('downstream-domain')
        cls.downstream_domain = cls.downstream_domain_obj.name

    @classmethod
    def tearDownClass(cls):
        super(CreateLinkedAppTest, cls).tearDownClass()
        cls.upstream_domain_obj.delete()
        cls.downstream_domain_obj.delete()

    def test_create_linked_app_succeeds(self):
        domain_link = DomainLink(linked_domain=self.downstream_domain, master_domain=self.upstream_domain)
        domain_link.save()
        self.addCleanup(domain_link.delete)

        app_name = "Original Application"
        app = Application.new_app(self.upstream_domain, app_name)
        app.save()
        self.addCleanup(app.delete)

        linked_app = link_app_in_existing_domain_link(domain_link.id, app._id)

        self.assertEqual('LinkedApplication', linked_app.get_doc_type())
        self.assertEqual(app._id, linked_app.upstream_app_id)
        self.assertEqual(app_name, linked_app.name)

    def test_create_linked_app_returns_none_if_no_link(self):
        app = Application.new_app(self.upstream_domain, "Original Application")
        app.save()
        self.addCleanup(app.delete)

        linked_app = link_app_in_existing_domain_link(None, app._id)

        self.assertIsNone(linked_app)

    def test_create_linked_app_raises_exception_if_no_app(self):
        domain_link = DomainLink(linked_domain=self.downstream_domain, master_domain=self.upstream_domain)
        domain_link.save()
        self.addCleanup(domain_link.delete)

        with self.assertRaises(Http404):
            link_app_in_existing_domain_link(domain_link, 'abc123')
