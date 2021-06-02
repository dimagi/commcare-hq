import re
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from requests import HTTPError

from corehq.apps.data_dictionary.models import CaseType
from corehq.motech.auth import AuthManager
from corehq.motech.const import COMMCARE_DATA_TYPE_TEXT
from corehq.motech.exceptions import RemoteAPIError
from corehq.motech.models import ConnectionSettings
from corehq.motech.requests import Requests
from corehq.util.test_utils import flag_enabled

from ..const import (
    FHIR_DATA_TYPE_LIST_OF_STRING,
    FHIR_VERSION_4_0_1,
    SYSTEM_URI_CASE_ID,
)
from ..models import (
    FHIRImporter,
    FHIRImporterResourceProperty,
    FHIRImporterResourceType,
    JSONPathToResourceType,
)
from ..tasks import (
    ServiceRequestNotActive,
    claim_service_request,
    get_case_id_or_none,
    get_caseblock_kwargs,
    get_name,
    import_related,
    import_resource,
    run_importer,
)

DOMAIN = 'test-domain'


class TestRunImporter(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Test ConnectionSettings',
            url='https://example.com/api/',
        )
        cls.fhir_importer = FHIRImporter.objects.create(
            domain=DOMAIN,
            connection_settings=cls.conn,
            fhir_version=FHIR_VERSION_4_0_1,
        )
        cls.mother = CaseType.objects.create(
            domain=DOMAIN,
            name='mother',
        )
        cls.referral = CaseType.objects.create(
            domain=DOMAIN,
            name='referral',
        )

    @classmethod
    def tearDownClass(cls):
        cls.referral.delete()
        cls.mother.delete()
        cls.fhir_importer.delete()
        cls.conn.delete()
        super().tearDownClass()

    @flag_enabled('FHIR_INTEGRATION')
    def test_import_related_only(self):
        import_me = FHIRImporterResourceType.objects.create(
            fhir_importer=self.fhir_importer,
            name='ServiceRequest',
            case_type=self.referral,
            search_params={'status': 'active'},
        )
        FHIRImporterResourceType.objects.create(
            fhir_importer=self.fhir_importer,
            name='Patient',
            case_type=self.mother,
            import_related_only=True,  # Don't import me
        )
        with patch('corehq.motech.fhir.tasks.import_resource_type') as import_resource_type:
            run_importer(self.fhir_importer)

            import_resource_type.assert_called_once()
            call_arg_2 = import_resource_type.call_args[0][1]
            self.assertEqual(call_arg_2, import_me)


class TestClaimServiceRequest(TestCase):

    service_request = {
        'id': '12345',
        'resourceType': 'ServiceRequest',
        'status': 'active',
    }

    def setUp(self):
        self.no_auth = AuthManager()

    def test_service_request_404(self):
        with patch.object(Requests, 'get') as requests_get:
            requests_get.side_effect = HTTPError('Client Error: 404')
            requests = Requests(
                DOMAIN,
                'https://example.com/api',
                auth_manager=self.no_auth,
                logger=lambda level, entry: None,
            )

            with self.assertRaises(HTTPError):
                claim_service_request(requests, self.service_request, '0f00')

    def test_service_request_500(self):
        with patch.object(Requests, 'get') as requests_get:
            requests_get.side_effect = HTTPError('Server Error: 500')
            requests = Requests(
                DOMAIN,
                'https://example.com/api',
                auth_manager=self.no_auth,
                logger=lambda level, entry: None,
            )

            with self.assertRaises(HTTPError):
                claim_service_request(requests, self.service_request, '0f00')

    def test_service_request_on_hold(self):
        response = ServiceRequestResponse('on-hold')
        with patch.object(Requests, 'get') as requests_get:
            requests_get.return_value = response
            requests = Requests(
                DOMAIN,
                'https://example.com/api',
                auth_manager=self.no_auth,
                logger=lambda level, entry: None,
            )

            with self.assertRaises(ServiceRequestNotActive):
                claim_service_request(requests, self.service_request, '0f00')

    def test_service_request_completed(self):
        response = ServiceRequestResponse('completed')
        with patch.object(Requests, 'get') as requests_get:
            requests_get.return_value = response
            requests = Requests(
                DOMAIN,
                'https://example.com/api',
                auth_manager=self.no_auth,
                logger=lambda level, entry: None,
            )

            with self.assertRaises(ServiceRequestNotActive):
                claim_service_request(requests, self.service_request, '0f00')

    def test_service_request_claimed(self):
        response = ServiceRequestResponse()
        with patch.object(Requests, 'get') as requests_get, \
                patch.object(Requests, 'put') as requests_put:
            requests_get.return_value = response
            requests_put.return_value = response
            requests = Requests(
                DOMAIN,
                'https://example.com/api',
                auth_manager=self.no_auth,
                logger=lambda level, entry: None,
            )
            resource = claim_service_request(
                requests,
                self.service_request,
                '0f00',
            )
            self.assertEqual(resource, response.service_request)

    def test_service_request_412(self):
        response_active = ServiceRequestResponse()
        response_on_hold = ServiceRequestResponse('on-hold')
        response_412 = ServiceRequestResponse()
        response_412.status = 412

        with patch.object(Requests, 'get') as requests_get, \
                patch.object(Requests, 'put') as requests_put:
            requests_get.side_effect = [
                response_active,  # First call: Ready to be claimed
                response_on_hold,  # Recursion: Claimed by other CHIS
            ]
            requests_put.return_value = response_412
            requests = Requests(
                DOMAIN,
                'https://example.com/api',
                auth_manager=self.no_auth,
                logger=lambda level, entry: None,
            )
            with self.assertRaises(ServiceRequestNotActive):
                claim_service_request(requests, self.service_request, '0f00')


class ServiceRequestResponse:

    status = 200
    headers = {'ETag': 'W/"123"'}

    def __init__(self, status='active'):
        self.service_request = {
            'id': '12345',
            'resourceType': 'ServiceRequest',
            'status': status,
        }

    def json(self):
        return self.service_request


class TestImportResource(SimpleTestCase):

    def test_bad_resource(self):
        with self.assertRaises(RemoteAPIError):
            import_resource(
                requests=None,
                resource_type=FooResourceType(),
                resource={},
            )

    def test_bad_resource_type(self):
        with self.assertRaises(RemoteAPIError):
            import_resource(
                requests=None,
                resource_type=FooResourceType(),
                resource={'resourceType': 'Bar'},
            )


class FooResourceType:
    name = 'Foo'


class TestImportRelated(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Test ConnectionSettings',
            url='https://example.com/api/',
        )
        cls.fhir_importer = FHIRImporter.objects.create(
            domain=DOMAIN,
            connection_settings=cls.conn,
            fhir_version=FHIR_VERSION_4_0_1,
        )
        cls.referral = CaseType.objects.create(
            domain=DOMAIN,
            name='referral',
        )
        cls.mother = CaseType.objects.create(
            domain=DOMAIN,
            name='mother',
        )

        cls.service_request = FHIRImporterResourceType.objects.create(
            fhir_importer=cls.fhir_importer,
            name='ServiceRequest',
            case_type=cls.referral,
        )
        patient = FHIRImporterResourceType.objects.create(
            fhir_importer=cls.fhir_importer,
            name='Patient',
            case_type=cls.mother,
        )
        JSONPathToResourceType.objects.create(
            resource_type=cls.service_request,
            jsonpath='$.subject.reference',
            related_resource_type=patient,
        )

    @classmethod
    def tearDownClass(cls):
        cls.mother.delete()
        cls.referral.delete()
        cls.fhir_importer.delete()
        cls.conn.delete()
        super().tearDownClass()

    def test_import_related_calls_get_resource_with_reference(self):
        patient = {
            'id': '12345',
            'resourceType': 'Patient',
            'name': [{'text': 'Alice Apple'}]
        }
        service_request = {
            'id': '67890',
            'resourceType': 'ServiceRequest',
            'subject': {
                'reference': 'Patient/12345',
                'display': 'Alice Apple',
            },
            'status': 'active',
            'intent': 'directive',
            'priority': 'routine',
        }

        with patch('corehq.motech.fhir.tasks.get_resource') as get_resource, \
                patch('corehq.motech.fhir.tasks.import_resource'):
            get_resource.return_value = patient

            import_related(
                requests=None,
                resource_type=self.service_request,
                resource=service_request,
            )
            call_arg_2 = get_resource.call_args[0][1]
            self.assertEqual(call_arg_2, 'Patient/12345')


class TestGetCaseIDOrNone(SimpleTestCase):

    def test_no_identifier(self):
        resource = {'resourceType': 'Patient'}
        self.assertIsNone(get_case_id_or_none(resource))

    def test_identifier_not_case_id(self):
        resource = {
            'resourceType': 'Patient',
            'identifier': [{'system': 'foo', 'value': 'bar'}]
        }
        self.assertIsNone(get_case_id_or_none(resource))

    def test_identifier_is_case_id(self):
        resource = {
            'resourceType': 'Patient',
            'identifier': [
                {'system': 'foo', 'value': 'bar'},
                {'system': SYSTEM_URI_CASE_ID, 'value': 'abc123'},
            ]
        }
        self.assertEqual(get_case_id_or_none(resource), 'abc123')


class TestGetName(SimpleTestCase):

    def test_name_text(self):
        resource = {'name': [{'text': 'Alice APPLE'}]}
        self.assertEqual(get_name(resource), 'Alice APPLE')

    def test_name_no_text(self):
        resource = {'name': [{'family': 'Apple', 'given': ['Alice']}]}
        self.assertEqual(get_name(resource), '')

    def test_code_text(self):
        resource = {'code': [{
            'text': 'Negative for Chlamydia Trachomatis rRNA',
        }]}
        self.assertEqual(
            get_name(resource),
            'Negative for Chlamydia Trachomatis rRNA',
        )

    def test_code_no_text(self):
        resource = {'code': [{
            'system': 'http://snomed.info/sct',
            'code': '260385009',
        }]}
        self.assertEqual(get_name(resource), '')

    def test_got_nothing(self):
        resource = {'foo': 'bar'}
        self.assertEqual(get_name(resource), '')


class TestGetCaseBlockKwargs(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Test ConnectionSettings',
            url='https://example.com/api/',
        )
        cls.fhir_importer = FHIRImporter.objects.create(
            domain=DOMAIN,
            connection_settings=cls.conn,
            fhir_version=FHIR_VERSION_4_0_1,
        )
        cls.mother = CaseType.objects.create(
            domain=DOMAIN,
            name='mother',
        )
        cls.patient = FHIRImporterResourceType.objects.create(
            fhir_importer=cls.fhir_importer,
            name='Patient',
            case_type=cls.mother,
        )

    @classmethod
    def tearDownClass(cls):
        cls.mother.delete()
        cls.fhir_importer.delete()
        cls.conn.delete()
        super().tearDownClass()

    def test_update_case_name(self):
        resource = {
            'name': [{
                'given': ['Alice', 'Amelia', 'Anna'],
                'family': 'Apple',
                'text': 'Alice APPLE',
            }],
        }
        FHIRImporterResourceProperty.objects.create(
            resource_type=self.patient,
            value_source_config={
                'jsonpath': '$.name[0].given',
                'case_property': 'case_name',
                'external_data_type': FHIR_DATA_TYPE_LIST_OF_STRING,
                'commcare_data_type': COMMCARE_DATA_TYPE_TEXT,
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient, resource),
            {'case_name': 'Alice Amelia Anna', 'update': {}},
        )

    def test_default_case_name(self):
        resource = {
            'name': [{
                'given': ['Alice', 'Amelia', 'Anna'],
                'family': 'Apple',
                'text': 'Alice APPLE',
            }],
        }
        self.assertEqual(
            get_caseblock_kwargs(self.patient, resource),
            {'case_name': 'Alice APPLE', 'update': {}},
        )

    def test_missing_value(self):
        resource = {
            'name': [{
                'text': 'John',
            }],
        }
        FHIRImporterResourceProperty.objects.create(
            resource_type=self.patient,
            value_source_config={
                'jsonpath': '$.name[0].given',
                'case_property': 'case_name',
                'external_data_type': FHIR_DATA_TYPE_LIST_OF_STRING,
                'commcare_data_type': COMMCARE_DATA_TYPE_TEXT,
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient, resource),
            {'case_name': 'John', 'update': {}},
        )

    def test_non_case_property(self):
        resource = {
            'telecom': [{
                'system': 'phone',
                'value': '555-1234',
            }],
        }
        FHIRImporterResourceProperty.objects.create(
            resource_type=self.patient,
            value_source_config={
                'jsonpath': '$.telecom[0].system',
                'value': 'phone',
            }
        )
        FHIRImporterResourceProperty.objects.create(
            resource_type=self.patient,
            value_source_config={
                'jsonpath': '$.telecom[0].value',
                'case_property': 'phone_number',
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient, resource),
            {'case_name': '', 'update': {'phone_number': '555-1234'}},
        )

    def test_case_id(self):
        resource = {
            'identifier': [{
                'system': SYSTEM_URI_CASE_ID,
                'value': '12345'
            }]
        }
        FHIRImporterResourceProperty.objects.create(
            resource_type=self.patient,
            value_source_config={
                'jsonpath': '$.identifier[0].system',
                'value': SYSTEM_URI_CASE_ID,
            }
        )
        FHIRImporterResourceProperty.objects.create(
            resource_type=self.patient,
            value_source_config={
                'jsonpath': '$.identifier[0].value',
                'case_property': 'case_id',
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient, resource),
            {'case_name': '', 'update': {}},
        )

    def test_external_id(self):
        resource = {
            'id': '12345',
        }
        FHIRImporterResourceProperty.objects.create(
            resource_type=self.patient,
            value_source_config={
                'jsonpath': '$.id',
                'case_property': 'external_id',
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient, resource),
            {'case_name': '', 'update': {}},
        )
