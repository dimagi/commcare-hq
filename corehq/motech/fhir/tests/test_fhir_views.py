from datetime import datetime
from uuid import uuid4

from django.test import RequestFactory, TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.api.resources.auth import LoginAuthentication

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import HQApiKey, WebUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseIndexSQL
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
PERSON_CASE_ID = uuid4().hex
DELETED_CASE_ID = uuid4().hex
TEST_CASE_ID = uuid4().hex


class BaseFHIRViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN, use_sql_backend=True)
        cls.user = WebUser.create(DOMAIN, USERNAME, PASSWORD,
                                  created_by=None, created_via=None)
        cls.django_user = WebUser.get_django_user(cls.user)
        cls.api_key = HQApiKey.objects.create(user=cls.django_user)

        _setup_cases(owner_id=cls.user.user_id)
        _setup_mappings()

    @classmethod
    def tearDownClass(cls):
        delete_all_cases()
        cls.api_key.delete()
        cls.user.delete(deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def _get_response(self, path):
        return self.client.get(
            path,
            HTTP_AUTHORIZATION=f'ApiKey {USERNAME}:{self.api_key.key}'
        )


class TestFHIRGetView(BaseFHIRViewTest):

    def test_flag_not_enabled(self):
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", PERSON_CASE_ID])
        response = self._get_response(url)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('FHIR_INTEGRATION')
    def test_unsupported_fhir_version(self):
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", TEST_CASE_ID])
        url = url.replace(FHIR_VERSION, 'A4')
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Unsupported FHIR version"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_missing_case_id(self):
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", 'just-a-case-id'])
        response = self._get_response(url)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('FHIR_INTEGRATION')
    def test_auth_bad_resource(self):
        # requesting for a patient i.e person but case id of a test case type
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", TEST_CASE_ID])
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Invalid Resource Type"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_get(self):
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", PERSON_CASE_ID])
        response = self._get_response(url)
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
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + f"?patient_id={PERSON_CASE_ID}"
        response = self._get_response(url)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('FHIR_INTEGRATION')
    def test_unsupported_fhir_version(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + f"?patient_id={PERSON_CASE_ID}"
        url = url.replace(FHIR_VERSION, 'A4')
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Unsupported FHIR version"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_no_patient_id(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"])
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Please pass patient_id"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_deleted_case(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + f"?patient_id={DELETED_CASE_ID}"
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': f"Patient with ID {DELETED_CASE_ID} was removed"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_missing_case_id(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + "?patient_id=just-a-case-id"
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Could not find patient with ID just-a-case-id"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_no_case_types_for_resource_type(self):
        url = reverse("fhir_search",
                      args=[DOMAIN, FHIR_VERSION, "DiagnosticReport"]) + f"?patient_id={PERSON_CASE_ID}"
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': f"Resource type DiagnosticReport not available on {DOMAIN}"}
        )

    @flag_enabled('FHIR_INTEGRATION')
    def test_search(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + f"?patient_id={PERSON_CASE_ID}"
        response = self._get_response(url)
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


class ViewsPermissionsTests(BaseFHIRViewTest):

    def test_api_key_authenticated(self):
        for url in (
            reverse("fhir_get_view",
                    args=[DOMAIN, FHIR_VERSION, "Patient", PERSON_CASE_ID]),
            reverse("fhir_search",
                    args=[DOMAIN, FHIR_VERSION, "Observation"])
        ):
            request = _get_request(url, self.django_user, self.api_key.key)
            is_authenticated = LoginAuthentication().is_authenticated(request)
            self.assertTrue(is_authenticated)

    def test_superuser_not_authenticated(self):
        self.django_user.is_superuser = True
        self.django_user.save()

        for url in (
            reverse("fhir_get_view",
                    args=[DOMAIN, FHIR_VERSION, "Patient", PERSON_CASE_ID]),
            reverse("fhir_search",
                    args=[DOMAIN, FHIR_VERSION, "Observation"])
        ):
            request = _get_request(url, self.django_user)
            is_authenticated = LoginAuthentication().is_authenticated(request)
            self.assertFalse(is_authenticated)


def _setup_cases(owner_id):
    submit_case_blocks([
        _get_caseblock(PERSON_CASE_ID, 'person', owner_id, {'first_name': 'Fred'}).as_text(),
        _get_caseblock(DELETED_CASE_ID, 'person', owner_id).as_text(),
        _get_caseblock(TEST_CASE_ID, 'test', owner_id).as_text(),
    ], DOMAIN)

    case_accessor = CaseAccessors(DOMAIN)
    case_accessor.soft_delete_cases(
        [DELETED_CASE_ID], datetime.utcnow(), 'test-deletion-with-cases'
    )

    test_case = case_accessor.get_case(TEST_CASE_ID)
    test_case.track_create(CommCareCaseIndexSQL(
        case=test_case,
        identifier='parent',
        referenced_type='person',
        referenced_id=PERSON_CASE_ID,
        relationship_id=CommCareCaseIndexSQL.CHILD
    ))
    case_accessor.db_accessor.save_case(test_case)


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


def _get_request(path, user, api_key=None):
    if api_key:
        extra = {'HTTP_AUTHORIZATION': f'ApiKey {USERNAME}:{api_key}'}
    else:
        extra = {}
    request = RequestFactory().get(path, **extra)
    request.domain = DOMAIN
    request.user = user
    return request
