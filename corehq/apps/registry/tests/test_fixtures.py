from unittest.mock import patch
from xml.etree import ElementTree

from django.test import SimpleTestCase, TestCase

from casexml.apps.phone.tests.utils import call_fixture_generator, create_restore_user
from corehq.apps.app_manager.models import CaseSearchProperty
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.registry.fixtures import (
    _get_registry_list_fixture,
    _get_registry_domains_fixture,
    registry_fixture_generator
)
from corehq.apps.registry.models import DataRegistry
from corehq.apps.registry.tests.utils import create_registry_for_test, Invitation, Grant
from corehq.util.test_utils import flag_enabled


class RegistryFixtureProviderTests(TestCase, TestXmlMixin):
    @classmethod
    def setUpTestData(cls):
        cls.domain = "registry-fixture-test"
        cls.domain_obj = create_domain(cls.domain)
        cls.domain_obj.hr_name = "Registry Fixture Test"
        cls.domain_obj.save()
        cls.restore_user = create_restore_user(cls.domain, username=f'{cls.domain}-user')
        cls.restore_user_domain_1 = create_restore_user("domain1", username='domain1-user')

        invitations = [Invitation("domain1"), Invitation("domain2")]
        grants = [Grant("domain1", [cls.domain]), Grant("domain2", [cls.domain])]
        cls.registry = create_registry_for_test(
            cls.restore_user._couch_user.get_django_user(), cls.domain,
            invitations=invitations, grants=grants, name="Test Registry"
        )
        factory = AppFactory(domain=cls.domain)
        module1, form1 = factory.new_basic_module("patient", "patient")
        module1.search_config.properties = [CaseSearchProperty()]
        module1.search_config.data_registry = cls.registry.slug

        factory.new_report_module("reports")

        cls.app = factory.app
        cls.app.save()

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        cls.registry.delete()
        cls.restore_user._couch_user.delete(None, None)
        cls.restore_user_domain_1._couch_user.delete(None, None)
        Domain.get_db().delete_doc(cls.domain_obj.get_id)
        super().tearDownClass()

    def test_fixture_provider_flag_disabled(self):
        fixtures = call_fixture_generator(
            registry_fixture_generator, self.restore_user, project=Domain(name="domain1")
        )
        self.assertEqual([], fixtures)

    @flag_enabled("DATA_REGISTRY")
    def test_fixture_provider_no_apps(self):
        fixtures = call_fixture_generator(
            registry_fixture_generator, self.restore_user_domain_1
        )
        self.assertEqual([], fixtures)

    @flag_enabled("DATA_REGISTRY")
    @patch("corehq.apps.registry.fixtures._get_permission_checker")
    def test_fixture_provider_no_permission(self, _get_permission_checker):
        _get_permission_checker().can_view_registry_data.return_value = False
        fixtures = call_fixture_generator(
            registry_fixture_generator, self.restore_user, project=self.domain_obj
        )
        self.assertEqual(1, len(fixtures))
        expected_list_fixture = """
        <fixture id="registry:list">
           <registry_list></registry_list>
        </fixture>"""
        self.assertXmlEqual(expected_list_fixture, ElementTree.tostring(fixtures[0], encoding='utf-8'))

    @flag_enabled("DATA_REGISTRY")
    @patch("corehq.apps.registry.fixtures._get_permission_checker")
    def test_fixture_provider(self, _get_permission_checker):
        _get_permission_checker().can_view_registry_data.return_value = True
        list_fixture, domains_fixture = call_fixture_generator(
            registry_fixture_generator, self.restore_user, project=self.domain_obj
        )

        expected_list_fixture = f"""
        <fixture id="registry:list">
           <registry_list>
               <registry slug="{self.registry.slug}" owner="{self.domain}" active="true">
                   <name>{self.registry.name}</name>
                   <description></description>
               </registry>
           </registry_list>
        </fixture>"""

        expected_domains_fixture = f"""
        <fixture id="registry:domains:{self.registry.slug}">
           <domains>
               <domain name="domain1">domain1</domain>
               <domain name="domain2">domain2</domain>
               <domain name="{self.domain}">{self.domain_obj.hr_name}</domain>
           </domains>
        </fixture>
        """

        self.assertXmlEqual(expected_list_fixture, ElementTree.tostring(list_fixture, encoding='utf-8'))
        self.assertXmlEqual(expected_domains_fixture, ElementTree.tostring(domains_fixture, encoding='utf-8'))


class RegistryFixtureTests(SimpleTestCase, TestXmlMixin):
    def setUp(self):
        self.registry1 = DataRegistry(
            domain="domain_owner",
            name="Patient Registry",
            description="Registry of Malaria Patients",
            slug="reg1",
        )
        self.registry1.get_granted_domains = _mock_get_granted_domain({"domain1", "domain2"})

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

    def test_registry_domains_fixture(self):
        expected = """
        <fixture id="registry:domains:reg1">
           <domains>
               <domain name="domain1">domain1</domain>
               <domain name="domain2">Domain Number 2</domain>
           </domains>
        </fixture>
        """

        def _mock_get_domain(name):
            if name == "domain2":
                return Domain(hr_name="Domain Number 2")

        with patch.object(Domain, 'get_by_name', _mock_get_domain):
            fixture = _get_registry_domains_fixture("domain1", self.registry1)
        self.assertXmlEqual(expected, ElementTree.tostring(fixture, encoding='unicode'))


def _mock_get_granted_domain(domains):
    def _mock_fn(domain):
        return domains
    return _mock_fn
