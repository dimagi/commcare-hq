from xml.etree import ElementTree

from django.test import SimpleTestCase

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.registry.fixturegenerators import _get_registry_list_fixture
from corehq.apps.registry.models import DataRegistry


class RegistryFixtureTests(SimpleTestCase, TestXmlMixin):
    def setUp(self):
        self.registry1 = DataRegistry(
            domain="domain_owner",
            name="Patient Registry",
            description="Registry of Malaria Patients",
            slug="reg1",
        )

        self.registry2 = DataRegistry(
            domain="domain_owner_1",
            name="Contact Registry",
            description="Registry of Contacts",
            slug="contacts",
            is_active=False,
        )

    def test_registry_list_fixture(self):
        fixture = _get_registry_list_fixture([self.registry1, self.registry2])
        expected = """
        <fixture id="registry:list">
           <registry_list>
               <registry slug="reg1" owner="domain_owner" active="true">
                   <name>Patient Registry</name>
                   <description>Registry of Malaria Patients</description>
               </registry>
               <registry slug="contacts" owner="domain_owner_1" active="false">
                   <name>Contact Registry</name>
                   <description>Registry of Contacts</description>
               </registry>
           </registry_list>
        </fixture>"""
        self.assertXmlEqual(expected, ElementTree.tostring(fixture, encoding='unicode'))
