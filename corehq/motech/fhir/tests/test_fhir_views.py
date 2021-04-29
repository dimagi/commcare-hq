from base64 import b64encode
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    JsonResponse,
)
from django.test import TestCase
from django.urls import reverse

from bs4 import BeautifulSoup
from tastypie.http import HttpUnauthorized

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import HQApiKey, Permissions, UserRole, WebUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseIndexSQL
from corehq.motech.fhir.tests.utils import (
    add_case_property_with_resource_property_path,
    add_case_type_with_resource_type,
)
from corehq.motech.utils import get_endpoint_url
from corehq.util.test_utils import flag_enabled, privilege_enabled

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
        cls.role = UserRole.get_or_create_with_permissions(
            DOMAIN, Permissions(edit_data=True), 'edit-data'
        )
        cls.user = WebUser.create(
            DOMAIN, USERNAME, PASSWORD,
            created_by=None, created_via=None, role_id=cls.role.get_id,
        )
        cls.django_user = WebUser.get_django_user(cls.user)
        cls.api_key = HQApiKey.objects.create(user=cls.django_user)

        _setup_cases(owner_id=cls.user.user_id)
        _setup_mappings()

    @classmethod
    def tearDownClass(cls):
        delete_all_cases()
        cls.api_key.delete()
        cls.user.delete(deleted_by=None)
        cls.role.delete()
        cls.domain_obj.delete()
        super().tearDownClass()

    def _get_response(self, path):
        return self.client.get(
            path,
            HTTP_AUTHORIZATION=f'ApiKey {USERNAME}:{self.api_key.key}'
        )

    def assertHQStandard404Page(self, response):
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response['content-type'], 'text/html; charset=utf-8')
        title = BeautifulSoup(response.content).find('title')
        self.assertEqual(title.text, '\n'.join((
            '',
            '      404 Not Found',
            '      - ',
            '      CommCare HQ',
            '    '
        )))

    def assertHQUpgradeRequiredPage(self, response):
        self.assertEqual(response['content-type'], 'text/html; charset=utf-8')
        title = BeautifulSoup(response.content).find('title')
        self.assertEqual(title.text, '\n'.join((
            '',
            '      : Upgrade Required',
            '      - ',
            '      CommCare HQ',
            '    '
        )))


@flag_enabled('FHIR_INTEGRATION')
@privilege_enabled(privileges.API_ACCESS)
class TestFHIRGetView(BaseFHIRViewTest):
    """
    Tests to confirm the responses of ``fhir_get_view``
    """

    def test_unsupported_fhir_version(self):
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", TEST_CASE_ID])
        url = url.replace(FHIR_VERSION, 'A4')
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Unsupported FHIR version"}
        )

    def test_missing_case_id(self):
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", 'just-a-case-id'])
        response = self._get_response(url)
        self.assertHQStandard404Page(response)

    def test_auth_bad_resource(self):
        # requesting for a patient i.e person but case id of a test case type
        url = reverse("fhir_get_view", args=[DOMAIN, FHIR_VERSION, "Patient", TEST_CASE_ID])
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Invalid Resource Type"}
        )

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


@flag_enabled('FHIR_INTEGRATION')
@privilege_enabled(privileges.API_ACCESS)
class TestFHIRSearchView(BaseFHIRViewTest):
    """
    Tests to confirm the responses of the ``fhir_search`` view
    """

    def test_unsupported_fhir_version(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + f"?patient_id={PERSON_CASE_ID}"
        url = url.replace(FHIR_VERSION, 'A4')
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Unsupported FHIR version"}
        )

    def test_no_patient_id(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"])
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Please pass patient_id"}
        )

    def test_deleted_case(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + f"?patient_id={DELETED_CASE_ID}"
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': f"Patient with ID {DELETED_CASE_ID} was removed"}
        )

    def test_missing_case_id(self):
        url = reverse("fhir_search", args=[DOMAIN, FHIR_VERSION, "Observation"]) + "?patient_id=just-a-case-id"
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': "Could not find patient with ID just-a-case-id"}
        )

    def test_no_case_types_for_resource_type(self):
        url = reverse("fhir_search",
                      args=[DOMAIN, FHIR_VERSION, "DiagnosticReport"]) + f"?patient_id={PERSON_CASE_ID}"
        response = self._get_response(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'message': f"Resource type DiagnosticReport not available on {DOMAIN}"}
        )

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


class APIAuthenticationTests(BaseFHIRViewTest):
    """
    Tests to confirm the authentication requirements of the FHIR API.
    """

    api_endpoints = (
        reverse(
            "fhir_get_view",
            args=[DOMAIN, FHIR_VERSION, "Patient", PERSON_CASE_ID],
        ),
        reverse(
            "fhir_search",
            args=[DOMAIN, FHIR_VERSION, "Observation"],
        ),
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.username_cant_edit = f'joe.bloggs@{DOMAIN}.commcarehq.org'
        cls.user_cant_edit = WebUser.create(
            DOMAIN, cls.username_cant_edit, 'Passw0rd!',
            created_by=None, created_via=None,
        )
        django_user = WebUser.get_django_user(cls.user_cant_edit)
        cls.api_key_cant_edit = HQApiKey.objects.create(user=django_user)

    @classmethod
    def tearDownClass(cls):
        cls.api_key_cant_edit.delete()
        cls.user_cant_edit.delete(deleted_by=None)
        super().tearDownClass()

    @flag_enabled('FHIR_INTEGRATION')
    @privilege_enabled(privileges.API_ACCESS)
    def test_api_key_auth(self):
        for url in self.api_endpoints:
            response = self.client.get(
                url,
                HTTP_AUTHORIZATION=f'ApiKey {USERNAME}:{self.api_key.key}',
            )
            self.assertIsInstance(response, JsonResponse)

    @flag_enabled('FHIR_INTEGRATION')
    def test_api_key_auth_without_api_access(self):
        for url in self.api_endpoints:
            response = self.client.get(
                url,
                HTTP_AUTHORIZATION=f'ApiKey {USERNAME}:{self.api_key.key}',
            )
            self.assertIsInstance(response, HttpResponse)
            self.assertHQUpgradeRequiredPage(response)

    @privilege_enabled(privileges.API_ACCESS)
    def test_api_key_auth_without_fhir_integration(self):
        for url in self.api_endpoints:
            response = self.client.get(
                url,
                HTTP_AUTHORIZATION=f'ApiKey {USERNAME}:{self.api_key.key}',
            )
            self.assertIsInstance(response, HttpResponseNotFound)
            self.assertHQStandard404Page(response)

    @flag_enabled('FHIR_INTEGRATION')
    @privilege_enabled(privileges.API_ACCESS)
    def test_cant_edit_data(self):
        extra = {
            'HTTP_AUTHORIZATION':
                f'ApiKey {self.username_cant_edit}:{self.api_key_cant_edit.key}'
        }
        for url in self.api_endpoints:
            response = self.client.get(url, **extra)
            self.assertIsInstance(response, HttpResponseForbidden)

    def test_basic_auth(self):
        b64_bytes = b64encode(f'{USERNAME}:{PASSWORD}'.encode('utf8'))
        basic_auth = b64_bytes.decode('utf8')
        for url in self.api_endpoints:
            response = self.client.get(
                url,
                HTTP_AUTHORIZATION=f'Basic {basic_auth}',
            )
            self.assertIsInstance(response, HttpUnauthorized)

    def test_superuser_login(self):
        with user_is_superuser(self.django_user):
            for url in self.api_endpoints:
                response = self.client.get(url)
                self.assertIsInstance(response, HttpUnauthorized)


@flag_enabled('FHIR_INTEGRATION')
@privilege_enabled(privileges.API_ACCESS)
class APIAuthorizationTests(BaseFHIRViewTest):
    """
    Tests to confirm what API users are authorized to see.
    """

    other_domain = 'where-there-is-smhok'
    other_owner_id = uuid4().hex
    other_patient_id = uuid4().hex
    other_observation_id = uuid4().hex

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_domain_obj = create_domain(
            cls.other_domain,
            use_sql_backend=True,
        )
        cls._set_up_other_cases()

    @classmethod
    def _set_up_other_cases(cls):
        submit_case_blocks([
            _get_caseblock(
                cls.other_patient_id, 'person', cls.other_owner_id,
                {'first_name': 'Eilidh'}
            ).as_text(),
            _get_caseblock(
                cls.other_observation_id, 'test', cls.other_owner_id,
            ).as_text(),
        ], cls.other_domain)

        case_accessor = CaseAccessors(cls.other_domain)
        test_case = case_accessor.get_case(cls.other_observation_id)
        test_case.track_create(CommCareCaseIndexSQL(
            case=test_case,
            identifier='parent',
            referenced_type='person',
            referenced_id=cls.other_patient_id,
            relationship_id=CommCareCaseIndexSQL.CHILD
        ))
        case_accessor.db_accessor.save_case(test_case)

    @classmethod
    def tearDownClass(cls):
        cls.other_domain_obj.delete()
        super().tearDownClass()

    def test_get(self):
        url = reverse("fhir_get_view", args=[
            DOMAIN, FHIR_VERSION, "Patient", self.other_patient_id
        ])
        response = self._get_response(url)
        self.assertHQStandard404Page(response)

    def test_search(self):
        url = reverse("fhir_search", args=[
            DOMAIN, FHIR_VERSION, "Observation"
        ]) + f"?patient_id={self.other_patient_id}"
        response = self._get_response(url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {
            'message': f'Could not find patient with ID {self.other_patient_id}'
        })


@contextmanager
def user_is_superuser(user):
    is_superuser = user.is_superuser
    try:
        user.is_superuser = True
        yield
    finally:
        user.is_superuser = is_superuser


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
