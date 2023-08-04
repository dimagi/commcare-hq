from datetime import datetime
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.motech.fhir.tests.utils import (
    add_case_property_with_resource_property_path,
    add_case_type_with_resource_type,
)
from corehq.motech.utils import get_endpoint_url
from corehq.util.test_utils import flag_enabled

DOMAIN = 'fhir-drill'
FHIR_VERSION = 'R4'
BASE_URL = f'http://localhost:8000/a/{DOMAIN}/fhir/{FHIR_VERSION}/'
USERNAME = f'admin@{DOMAIN}.commcarehq.org'
PASSWORD = 'Passw0rd!'
PERSON_CASE_ID = str(uuid4())
DELETED_CASE_ID = str(uuid4())
TEST_CASE_ID = str(uuid4())


class BaseFHIRViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.user = WebUser.create(DOMAIN, USERNAME, PASSWORD,
                                  created_by=None, created_via=None)
        # ToDo: to be removed according to authentication updates by Smart-On-Fhir work
        cls.user.is_superuser = True
        cls.user.save()

        _setup_cases(owner_id=cls.user.user_id)
        _setup_mappings()

    def setUp(self):
        super().setUp()
        self.client.login(username=USERNAME, password=PASSWORD)

    @classmethod
    def tearDownClass(cls):
        delete_all_cases()
        delete_username(cls.domain_obj.name, USERNAME)
        cls.domain_obj.delete()
        super().tearDownClass()


def delete_username(domain, username):
    user = WebUser.get_by_username(username)
    if user:
        user.delete(domain, deleted_by=None)


class TestFHIRGetView(BaseFHIRViewTest):
    def test_flag_not_enabled(self):
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", PERSON_CASE_ID])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('FHIR_INTEGRATION')
    def test_unsupported_fhir_version(self):
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", TEST_CASE_ID])
        url = url.replace(FHIR_VERSION, 'A4')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Unsupported FHIR version"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_missing_case_id(self):
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", 'just-a-case-id'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('FHIR_INTEGRATION')
    def test_auth_bad_resource(self):
        # requesting for a patient i.e person but case id of a test case type
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", TEST_CASE_ID])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Invalid Resource Type"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_get(self):
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", PERSON_CASE_ID])
        response = self.client.get(url)
        response_json = response.json()
        self.assertEqual(
            response_json,
            {
                'id': PERSON_CASE_ID,
                'resourceType': 'Patient',
                'name': [{'given': ['Fred']}]
            }
        )


class TestFHIRSearchView(BaseFHIRViewTest):
    def test_flag_not_enabled(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + f"?_id={PERSON_CASE_ID}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('FHIR_INTEGRATION')
    def test_unsupported_fhir_version(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + f"?_id={PERSON_CASE_ID}"
        url = url.replace(FHIR_VERSION, 'A4')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Unsupported FHIR version"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_no_patient_id(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Please pass resource ID."}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_deleted_case(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + f"?_id={DELETED_CASE_ID}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 410)
        self.assertEqual(
            response.json(),
            {'message': "Gone"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_missing_case_id(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + "?_id=just-a-case-id"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {'message': "Not Found"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_no_case_types_for_resource_type(self):
        url = reverse("fhir_search",
                      args=[DOMAIN, FHIR_VERSION, "DiagnosticReport"]) + f"?_id={PERSON_CASE_ID}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': f"Resource type(s) DiagnosticReport not available on {DOMAIN}"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_search(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + f"?_id={PERSON_CASE_ID}"
        response = self.client.get(url)
        self.assertEqual(
            response.json(),
            {
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [
                    {
                        "fullUrl": get_endpoint_url(BASE_URL, f'/Observation/{TEST_CASE_ID}/'),
                        "search": {
                            "mode": "match"
                        }
                    }
                ]
            }
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_search_patient_using_patient_id(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Patient"]) + f"?patient_id={PERSON_CASE_ID}"
        response = self.client.get(url)
        self.assertEqual(
            response.json(),
            {
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [
                    {
                        "fullUrl": get_endpoint_url(BASE_URL, f'/Patient/{PERSON_CASE_ID}/'),
                        "search": {
                            "mode": "match"
                        }
                    }
                ]
            }
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_no_resource_provided(self):
        url = reverse("fhir_search_mulitple_types", args=[DOMAIN, FHIR_VERSION]) + f"?_id={PERSON_CASE_ID}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "No resource type specified for search."}
        )


def _setup_cases(owner_id):
    submit_case_blocks([
        _get_caseblock(PERSON_CASE_ID, 'person', owner_id, {'first_name': 'Fred'}).as_text(),
        _get_caseblock(DELETED_CASE_ID, 'person', owner_id).as_text(),
        _get_caseblock(TEST_CASE_ID, 'test', owner_id).as_text(),
    ], DOMAIN)

    CommCareCase.objects.soft_delete_cases(
        DOMAIN, [DELETED_CASE_ID], datetime.utcnow(), 'test-deletion-with-cases'
    )

    test_case = CommCareCase.objects.get_case(TEST_CASE_ID, DOMAIN)
    test_case.track_create(CommCareCaseIndex(
        case=test_case,
        identifier='parent',
        referenced_type='person',
        referenced_id=PERSON_CASE_ID,
        relationship_id=CommCareCaseIndex.CHILD
    ))
    test_case.save(with_tracked_models=True)


def _get_caseblock(case_id, case_type, owner_id, updates=None):
    return CaseBlock(
        create=True,
        case_id=case_id,
        case_type=case_type,
        owner_id=owner_id,
        update=updates
    )


def _setup_mappings():
    person_case_type, patient_resource_type = add_case_type_with_resource_type(DOMAIN, 'person', 'Patient')
    add_case_property_with_resource_property_path(person_case_type, 'first_name', patient_resource_type,
                                                  '$.name[0].given[0]')
    add_case_type_with_resource_type(DOMAIN, 'test', 'Observation')
