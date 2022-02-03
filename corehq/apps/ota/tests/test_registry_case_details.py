from unittest.mock import patch

from defusedxml import ElementTree
from django.test import TestCase, Client
from django.urls import reverse

from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.case_search.const import COMMCARE_PROJECT
from corehq.apps.case_search.models import CASE_SEARCH_REGISTRY_ID_KEY
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.registry.models import RegistryAuditLog
from corehq.apps.registry.tests.utils import create_registry_for_test
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.models import XFormInstance
from corehq.util.test_utils import generate_cases, flag_enabled


@flag_enabled("DATA_REGISTRY")
@flag_enabled("SYNC_SEARCH_CASE_CLAIM")
class RegistryCaseDetailsTests(TestCase):
    domain = 'registry-case-details'

    @classmethod
    def setUpTestData(cls):
        cls.domain_object = create_domain(cls.domain)
        cls.user = CommCareUser.create(cls.domain, "user", "123", None, None)
        cls.registry = create_registry_for_test(cls.user.get_django_user(), cls.domain)
        cls.registry.schema = [{"case_type": "parent"}, {"case_type": "other"}]
        cls.registry.save()

        cls.grand_parent_case_id = 'mona'
        cls.parent_case_id = 'homer'
        cls.child_case_id = 'bart'
        grand_parent_case = CaseStructure(
            case_id=cls.grand_parent_case_id,
            attrs={'create': True, 'case_type': 'grandparent'},
        )

        parent_case = CaseStructure(
            case_id=cls.parent_case_id,
            attrs={'create': True, 'case_type': 'parent'},
            indices=[CaseIndex(
                grand_parent_case,
                identifier='parent',
            )],
        )

        child_case = CaseStructure(
            case_id=cls.child_case_id,
            attrs={'create': True, 'case_type': 'child'},
            indices=[CaseIndex(
                parent_case,
                identifier='host',
                relationship='extension'
            )],
        )

        cls.cases = CaseFactory(cls.domain).create_or_update_cases([child_case])
        cls.other_case = CaseFactory(cls.domain).create_or_update_case(
            CaseStructure(
                case_id='unrelated_case',
                attrs={'create': True, 'case_type': 'other'},
            )
        )

        cls.app = AppFactory(cls.domain).app
        cls.app.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by_domain=None, deleted_by=None)
        xform_ids = CaseAccessorSQL.get_case_xform_ids(cls.parent_case_id)
        CaseAccessorSQL.hard_delete_cases(cls.domain, [case.case_id for case in cls.cases])
        XFormInstance.objects.hard_delete_forms(cls.domain, xform_ids)
        cls.app.delete()
        Domain.get_db().delete_doc(cls.domain_object)  # no need to run the full domain delete
        super().tearDownClass()

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.login(username="user", password="123")

    def test_get_case_details(self):
        response_content = self._make_request({
            CASE_SEARCH_REGISTRY_ID_KEY: self.registry.slug, "case_id": self.parent_case_id, "case_type": "parent",
        }, 200)
        actual_cases = self._get_cases_in_response(response_content)
        expected_cases = {case.case_id: case for case in self.cases}
        self.assertEqual(set(actual_cases), set(expected_cases))

        actual_domains = {
            case.case_id: case.get_property(COMMCARE_PROJECT) for case in actual_cases.values()
        }
        expected_domains = {case.case_id: case.domain for case in self.cases}
        self.assertEqual(actual_domains, expected_domains)

        self.assertEqual(1, RegistryAuditLog.objects.filter(
            registry=self.registry,
            action=RegistryAuditLog.ACTION_DATA_ACCESSED,
            related_object_type=RegistryAuditLog.RELATED_OBJECT_APPLICATION,
            related_object_id=self.app.get_id
        ).count())

    def test_get_case_details_multiple_case_ids(self):
        response_content = self._make_request({
            CASE_SEARCH_REGISTRY_ID_KEY: self.registry.slug,
            "case_id": [self.parent_case_id, "unrelated_case"],
            "case_type": ["parent", "other"],
        }, 200)
        actual_cases = self._get_cases_in_response(response_content)
        expected_cases = {"unrelated_case": self.other_case, **{case.case_id: case for case in self.cases}}
        self.assertEqual(set(actual_cases), set(expected_cases))

    def test_get_case_details_post_request(self):
        response_content = self._make_request({
            CASE_SEARCH_REGISTRY_ID_KEY: self.registry.slug,
            "case_id": self.parent_case_id,
            "case_type": "parent",
        }, 200, method="post")
        actual_cases = self._get_cases_in_response(response_content)
        expected_cases = {case.case_id: case for case in self.cases}
        self.assertEqual(set(actual_cases), set(expected_cases))

    def test_get_case_details_missing_case(self):
        self._make_request({
            CASE_SEARCH_REGISTRY_ID_KEY: self.registry.slug, "case_id": "missing", "case_type": "parent",
        }, 404)

    def test_get_case_details_missing_registry(self):
        self._make_request({
            CASE_SEARCH_REGISTRY_ID_KEY: "not-a-registry", "case_id": self.parent_case_id, "case_type": "parent",
        }, 404)

    def _make_request(self, params, expected_response_code, method="get"):
        request_method = {
            "get": self.client.get,
            "post": self.client.post,
        }[method]
        with patch.object(DataRegistryHelper, '_check_user_has_access', return_value=True):
            response = request_method(reverse('registry_case', args=[self.domain, self.app.get_id]), data=params)
        content = response.content
        self.assertEqual(response.status_code, expected_response_code, content)
        return content.decode('utf8')

    def _get_cases_in_response(self, response_content):
        xml = ElementTree.fromstring(response_content)
        return {node.get('case_id'): _FixtureCase(node) for node in xml.findall("case")}


class _FixtureCase:
    """
    Shim class for working with XML case blocks in a case DB fixture.
    """
    def __init__(self, xml_element):
        self.xml_element = xml_element

    @property
    def case_id(self):
        return self.xml_element.get('case_id')

    def get_property(self, name):
        return self.xml_element.findtext(name)


@generate_cases([
    ({}, f"'case_id', 'case_type', '{CASE_SEARCH_REGISTRY_ID_KEY}' are required parameters"),
    ({"case_id": "a"}, f"'case_type', '{CASE_SEARCH_REGISTRY_ID_KEY}' are required parameters"),
    ({"case_id": "a", "case_type": "b"}, f"'{CASE_SEARCH_REGISTRY_ID_KEY}' is a required parameter"),
], RegistryCaseDetailsTests)
@flag_enabled("SYNC_SEARCH_CASE_CLAIM")
@flag_enabled("DATA_REGISTRY")
def test_required_params(self, params, message):
    content = self._make_request(params, 400)
    self.assertEqual(content, message)
