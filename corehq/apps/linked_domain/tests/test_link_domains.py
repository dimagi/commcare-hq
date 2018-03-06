from __future__ import absolute_import
from django.test import TestCase

from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.linked_domain.models import DomainLink


class LinkedDomainTests(TestCase):
    def tearDown(self):
        DomainLink.all_objects.all().delete()
        super(LinkedDomainTests, self).tearDown()

    def test_linking_existing(self):
        link = DomainLink.link_domains('linked', 'master')
        link1 = DomainLink.link_domains('linked', 'master')
        self.assertEqual(link.pk, link1.pk)

    def test_double_link(self):
        DomainLink.link_domains('linked', 'master')
        with self.assertRaises(DomainLinkError):
            DomainLink.link_domains('linked', 'master2')

    def test_multiple_master_links(self):
        link1 = DomainLink.link_domains('linked1', 'master')
        link2 = DomainLink.link_domains('linked2', 'master')

        self.assertNotEqual(link1.pk, link2.pk)

    def test_link_previously_deleted(self):
        link = DomainLink.link_domains('linked', 'master')
        link.deleted = True
        link.save()

        link1 = DomainLink.link_domains('linked', 'master')
        self.assertEqual(link.pk, link1.pk)
        self.assertFalse(link1.deleted)

    def test_link_new_master(self):
        link = DomainLink.link_domains('linked', 'master')
        link.deleted = True
        link.save()

        link1 = DomainLink.link_domains('linked', 'master1')
        self.assertNotEqual(link.pk, link1.pk)
