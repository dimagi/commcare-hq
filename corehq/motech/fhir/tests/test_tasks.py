from contextlib import contextmanager
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from requests import HTTPError

from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import create_case, delete_all_cases

from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.domain.shortcuts import create_domain
from corehq.motech.const import COMMCARE_DATA_TYPE_TEXT
from corehq.motech.exceptions import ConfigurationError, RemoteAPIError
from corehq.motech.models import ConnectionSettings
from corehq.util.test_utils import flag_enabled

from ..const import (
    FHIR_DATA_TYPE_LIST_OF_STRING,
    FHIR_VERSION_4_0_1,
    SYSTEM_URI_CASE_ID,
)
from ..models import (
    FHIRImportConfig,
    FHIRImportResourceProperty,
    FHIRImportResourceType,
    ResourceTypeRelationship,
)
from ..tasks import (
    ParentInfo,
    ServiceRequestNotActive,
    build_case_block,
    claim_service_request,
    create_parent_indices,
    get_case_by_external_id,
    get_case_by_id,
    get_case_id_or_none,
    get_caseblock_kwargs,
    get_name,
    import_related,
    import_resource,
    run_importer,
    validate_parent_ref,
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
        cls.import_config = FHIRImportConfig.objects.create(
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
        cls.import_config.delete()
        cls.conn.delete()
        super().tearDownClass()

    @flag_enabled('FHIR_INTEGRATION')
    def test_import_related_only(self):
        import_me = FHIRImportResourceType.objects.create(
            import_config=self.import_config,
            name='ServiceRequest',
            case_type=self.referral,
            search_params={'status': 'active'},
        )
        FHIRImportResourceType.objects.create(
            import_config=self.import_config,
            name='Patient',
            case_type=self.mother,
            import_related_only=True,  # Don't import me
        )
        with patch('corehq.motech.fhir.tasks.import_resource_type') \
                as import_resource_type:
            run_importer(self.import_config.id)

            import_resource_type.assert_called_once()
            call_arg_2 = import_resource_type.call_args[0][1]
            self.assertEqual(call_arg_2, import_me)


class TestClaimServiceRequest(TestCase):

    service_request = {
        'id': '12345',
        'resourceType': 'ServiceRequest',
        'status': 'active',
    }

    def test_service_request_404(self):
        requests = Mock()
        requests.get.side_effect = HTTPError('Client Error: 404')
        with self.assertRaises(HTTPError):
            claim_service_request(requests, self.service_request, '0f00')

    def test_service_request_500(self):
        requests = Mock()
        requests.get.side_effect = HTTPError('Server Error: 500')
        with self.assertRaises(HTTPError):
            claim_service_request(requests, self.service_request, '0f00')

    def test_service_request_on_hold(self):
        response = ServiceRequestResponse('on-hold')
        requests = Mock()
        requests.get.return_value = response
        with self.assertRaises(ServiceRequestNotActive):
            claim_service_request(requests, self.service_request, '0f00')

    def test_service_request_completed(self):
        response = ServiceRequestResponse('completed')
        requests = Mock()
        requests.get.return_value = response
        with self.assertRaises(ServiceRequestNotActive):
            claim_service_request(requests, self.service_request, '0f00')

    def test_service_request_claimed(self):
        response = ServiceRequestResponse()
        requests = Mock()
        requests.get.return_value = response
        requests.put.return_value = response
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
        response_412.status_code = 412
        requests = Mock()
        requests.get.side_effect = [
            response_active,  # First call: Ready to be claimed
            response_on_hold,  # Recursion: Claimed by other CHIS
        ]
        requests.put.return_value = response_412
        with self.assertRaises(ServiceRequestNotActive):
            claim_service_request(requests, self.service_request, '0f00')

    def test_service_request_always_412(self):
        response_412 = ServiceRequestResponse()
        response_412.status_code = 412
        requests = Mock()
        # lambda create a new ServiceRequestResponse so that
        # ServiceRequestResponse.json() returns a clean service_request:
        requests.get.side_effect = lambda *a, **kw: ServiceRequestResponse()
        requests.put.return_value = response_412
        with self.assertRaises(HTTPError):
            claim_service_request(requests, self.service_request, '0f00')

    def test_service_request_has_case_id(self):
        response = ServiceRequestResponse()
        response.service_request['identifier'] = [{
            'system': SYSTEM_URI_CASE_ID,
            'value': 'abcde',
        }]
        requests = Mock()
        requests.get.return_value = response
        requests.put.return_value = response
        resource = claim_service_request(
            requests,
            self.service_request,
            '0f00',
        )
        self.assertEqual(
            resource['identifier'], [{
                'system': SYSTEM_URI_CASE_ID,
                'value': 'abcde',
            }],
        )


class ServiceRequestResponse:

    status_code = 200
    headers = {'ETag': 'W/"123"'}

    def __init__(self, status='active'):
        self.service_request = {
            'id': '12345',
            'resourceType': 'ServiceRequest',
            'status': status,
        }

    def json(self):
        # return by reference so that changes are visible on
        # self.service_request
        return self.service_request

    def raise_for_status(self):
        if not 200 <= self.status_code < 300:
            raise HTTPError(f'{self.status_code}: Boom!')


class TestImportResource(SimpleTestCase):

    def test_bad_resource(self):
        with self.assertRaises(RemoteAPIError):
            import_resource(
                requests=None,
                resource_type=FooResourceType(),
                resource={},
                child_cases=[],
            )

    def test_bad_resource_type(self):
        with self.assertRaises(RemoteAPIError):
            import_resource(
                requests=None,
                resource_type=FooResourceType(),
                resource={'resourceType': 'Bar'},
                child_cases=[],
            )


class FooResourceType:
    name = 'Foo'


class TestCaseWithResourceType(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Test ConnectionSettings',
            url='https://example.com/api/',
        )
        cls.import_config = FHIRImportConfig.objects.create(
            domain=DOMAIN,
            connection_settings=cls.conn,
            fhir_version=FHIR_VERSION_4_0_1,
        )
        cls.mother = CaseType.objects.create(
            domain=DOMAIN,
            name='mother',
        )
        cls.patient_type = FHIRImportResourceType.objects.create(
            import_config=cls.import_config,
            name='Patient',
            case_type=cls.mother,
        )

    @classmethod
    def tearDownClass(cls):
        cls.mother.delete()
        cls.import_config.delete()
        cls.conn.delete()
        super().tearDownClass()


class TestCaseWithFHIRResources(TestCaseWithResourceType):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.referral = CaseType.objects.create(
            domain=DOMAIN,
            name='referral',
        )
        cls.service_request_type = FHIRImportResourceType.objects.create(
            import_config=cls.import_config,
            name='ServiceRequest',
            case_type=cls.referral,
        )
        cls.patient = {
            'id': '12345',
            'resourceType': 'Patient',
            'name': [{'text': 'Alice Apple'}]
        }
        cls.service_request = {
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

    @classmethod
    def tearDownClass(cls):
        cls.referral.delete()
        super().tearDownClass()


class TestImportRelated(TestCaseWithFHIRResources):

    def test_import_related_calls_get_resource_with_reference(self):
        ResourceTypeRelationship.objects.create(
            resource_type=self.service_request_type,
            jsonpath='$.subject.reference',
            related_resource_type=self.patient_type,
        )
        with patch('corehq.motech.fhir.tasks.get_resource') as get_resource, \
                patch('corehq.motech.fhir.tasks.import_resource'):
            get_resource.return_value = self.patient

            import_related(
                requests=None,
                resource_type=self.service_request_type,
                resource=self.service_request,
                case_id='1',
                child_cases=[],
            )
            call_arg_2 = get_resource.call_args[0][1]
            self.assertEqual(call_arg_2, 'Patient/12345')

    def test_import_related_is_parent(self):
        ResourceTypeRelationship.objects.create(
            resource_type=self.service_request_type,
            jsonpath='$.subject.reference',
            related_resource_type=self.patient_type,
            related_resource_is_parent=True,
        )
        with patch('corehq.motech.fhir.tasks.get_resource'), \
                patch('corehq.motech.fhir.tasks.import_resource'):
            child_cases = []

            import_related(
                requests=None,
                resource_type=self.service_request_type,
                resource=self.service_request,
                case_id='1',
                child_cases=child_cases,
            )

            self.assertEqual(child_cases, [ParentInfo(
                child_case_id='1',
                parent_ref='Patient/12345',
                parent_resource_type=self.patient_type,
            )])

    def test_import_related_is_not_parent(self):
        ResourceTypeRelationship.objects.create(
            resource_type=self.service_request_type,
            jsonpath='$.subject.reference',
            related_resource_type=self.patient_type,
        )
        with patch('corehq.motech.fhir.tasks.get_resource'), \
                patch('corehq.motech.fhir.tasks.import_resource'):
            child_cases = []

            import_related(
                requests=None,
                resource_type=self.service_request_type,
                resource=self.service_request,
                case_id='1',
                child_cases=child_cases,
            )

            self.assertEqual(child_cases, [])


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


class TestGetCaseById(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.factory = CaseFactory(domain=DOMAIN)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        self.case_id = str(uuid4())
        self.factory.create_or_update_case(CaseStructure(
            case_id=self.case_id,
            attrs={
                'create': True,
                'case_type': 'mother',
                'case_name': 'Alice APPLE',
                'owner_id': 'b0b',
            }
        ))

    def test_case_id_not_found(self):
        case = get_case_by_id(DOMAIN, '12345')
        self.assertIsNone(case)

    def test_domain_is_different(self):
        case = get_case_by_id('not-the-domain', self.case_id)
        self.assertIsNone(case)

    def test_case_is_deleted(self):
        case = get_case_by_id(DOMAIN, self.case_id)
        case.delete()

        case = get_case_by_id(DOMAIN, self.case_id)
        self.assertIsNone(case)

    def test_happy_path(self):
        case = get_case_by_id(DOMAIN, self.case_id)
        self.assertEqual(case.name, 'Alice APPLE')


class TestGetCaseByExternalId(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.factory = CaseFactory(domain=DOMAIN)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        case_id = str(uuid4())
        self.external_id = str(uuid4())
        self.factory.create_or_update_case(CaseStructure(
            case_id=case_id,
            attrs={
                'create': True,
                'case_type': 'mother',
                'case_name': 'Alice APPLE',
                'owner_id': 'b0b',
                'external_id': self.external_id,
            }
        ))

    def test_external_id_not_found(self):
        case = get_case_by_external_id(DOMAIN, '67890', 'mother')
        self.assertIsNone(case)

    def test_domain_is_different(self):
        case = get_case_by_external_id('not-the-domain', self.external_id, 'mother')
        self.assertIsNone(case)

    def test_case_type_is_different(self):
        case = get_case_by_external_id(DOMAIN, self.external_id, 'father')
        self.assertIsNone(case)

    def test_case_is_deleted(self):
        case = get_case_by_external_id(DOMAIN, self.external_id, 'mother')
        case.delete()

        case = get_case_by_external_id(DOMAIN, self.external_id, 'mother')
        self.assertIsNone(case)

    def test_happy_path(self):
        case = get_case_by_external_id(DOMAIN, self.external_id, 'mother')
        self.assertEqual(case.name, 'Alice APPLE')


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


class TestGetCaseBlockKwargs(TestCaseWithResourceType):

    def test_update_case_name(self):
        resource = {
            'name': [{
                'given': ['Alice', 'Amelia', 'Anna'],
                'family': 'Apple',
                'text': 'Alice APPLE',
            }],
        }
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': '$.name[0].given',
                'case_property': 'case_name',
                'external_data_type': FHIR_DATA_TYPE_LIST_OF_STRING,
                'commcare_data_type': COMMCARE_DATA_TYPE_TEXT,
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient_type, resource),
            {'case_name': 'Alice Amelia Anna', 'update': {}},
        )

    def test_update_name(self):
        resource = {
            'name': [{
                'given': ['Alice', 'Amelia', 'Anna'],
                'family': 'Apple',
                'text': 'Alice APPLE',
            }],
        }
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': '$.name[0].given',
                'case_property': 'name',
                'external_data_type': FHIR_DATA_TYPE_LIST_OF_STRING,
                'commcare_data_type': COMMCARE_DATA_TYPE_TEXT,
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient_type, resource),
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
            get_caseblock_kwargs(self.patient_type, resource),
            {'case_name': 'Alice APPLE', 'update': {}},
        )

    def test_missing_value(self):
        resource = {
            'name': [{
                'text': 'John',
            }],
        }
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': '$.name[0].given',
                'case_property': 'case_name',
                'external_data_type': FHIR_DATA_TYPE_LIST_OF_STRING,
                'commcare_data_type': COMMCARE_DATA_TYPE_TEXT,
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient_type, resource),
            {'case_name': 'John', 'update': {}},
        )

    def test_non_case_property(self):
        resource = {
            'telecom': [{
                'system': 'phone',
                'value': '555-1234',
            }],
        }
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': '$.telecom[0].system',
                'value': 'phone',
            }
        )
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': '$.telecom[0].value',
                'case_property': 'phone_number',
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient_type, resource),
            {'case_name': '', 'update': {'phone_number': '555-1234'}},
        )

    def test_case_id(self):
        resource = {
            'identifier': [{
                'system': SYSTEM_URI_CASE_ID,
                'value': '12345'
            }]
        }
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': f"$.identifier[?system='{SYSTEM_URI_CASE_ID}'].value",
                'case_property': 'case_id',
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient_type, resource),
            {'case_name': '', 'update': {}},
        )

    def test_external_id(self):
        resource = {
            'id': '12345',
        }
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': '$.id',
                'case_property': 'external_id',
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient_type, resource),
            {'case_name': '', 'update': {}},
        )

    def test_readonly(self):
        resource = {
            'extension': [
                {
                    'url': 'https://example.com/commcare/case_type',
                    'value': 'foo',
                },
                {
                    'url': 'https://example.com/commcare/type',
                    'value': 'bar',
                },
                {
                    'url': 'https://example.com/commcare/user_id',
                    'value': '12345',
                },
                {
                    'url': 'https://example.com/commcare/owner_id',
                    'value': '12345',
                },
                {
                    'url': 'https://example.com/commcare/opened_on',
                    'value': '2021-07-02T17:00:00.000Z',
                },
                {
                    'url': 'https://example.com/commcare/this_is_fine',
                    'value': 'baz',
                },
            ],
        }
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': "$.extension[?url='https://example.com/commcare/case_type'].value",
                'case_property': 'case_type',
            }
        )
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': "$.extension[?url='https://example.com/commcare/type'].value",
                'case_property': 'type',
            }
        )
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': "$.extension[?url='https://example.com/commcare/user_id'].value",
                'case_property': 'user_id',
            }
        )
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': "$.extension[?url='https://example.com/commcare/owner_id'].value",
                'case_property': 'owner_id',
            }
        )
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': "$.extension[?url='https://example.com/commcare/opened_on'].value",
                'case_property': 'opened_on',
            }
        )
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': "$.extension[?url='https://example.com/commcare/this_is_fine'].value",
                'case_property': 'this_is_fine',
            }
        )
        self.assertEqual(
            get_caseblock_kwargs(self.patient_type, resource),
            {'case_name': '', 'update': {'this_is_fine': 'baz'}},
        )


class TestBuildCaseBlock(TestCaseWithResourceType):

    @classmethod
    def setUpClass(cls):
        cls.domain_obj = create_domain(DOMAIN)
        cls.factory = CaseFactory(domain=DOMAIN)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.domain_obj.delete()

    def tearDown(self):
        delete_all_cases()

    def test_resource_has_case_id(self):
        case_id = str(uuid4())
        suggested_case_id = str(uuid4())

        self.factory.create_or_update_case(CaseStructure(
            case_id=case_id,
            attrs={
                'create': True,
                'case_type': 'mother',
                'case_name': 'Alice APPLE',
                'owner_id': 'b0b',
            }
        ))
        resource = {
            'id': '12345',
            'identifier': [{
                'system': SYSTEM_URI_CASE_ID,
                'value': case_id,
            }],
            'resourceType': 'Patient',
        }

        case_block = build_case_block(
            self.patient_type,
            resource,
            suggested_case_id,
        )
        self.assertFalse(case_block.create)
        self.assertEqual(case_block.case_id, case_id)
        self.assertEqual(case_block.external_id, '12345')

    def test_resource_has_case_id_in_other_domain(self):
        case_id = str(uuid4())
        suggested_case_id = str(uuid4())

        with other_domain_factory('other-test-domain') as factory:
            factory.create_or_update_case(CaseStructure(
                case_id=case_id,
                attrs={
                    'create': True,
                    'case_type': 'mother',
                    'case_name': 'Alice APPLE',
                    'owner_id': 'b0b',
                }
            ))
            resource = {
                'identifier': [{
                    'system': SYSTEM_URI_CASE_ID,
                    'value': case_id,
                }],
                'resourceType': 'Patient',
            }

            case_block = build_case_block(
                self.patient_type,
                resource,
                suggested_case_id,
            )
            self.assertTrue(case_block.create)
            self.assertEqual(case_block.case_id, suggested_case_id)

    def test_resource_has_external_id(self):
        case_id = str(uuid4())
        suggested_case_id = str(uuid4())

        self.factory.create_or_update_case(CaseStructure(
            case_id=case_id,
            attrs={
                'create': True,
                'case_type': 'mother',
                'case_name': 'Alice APPLE',
                'owner_id': 'b0b',
                'external_id': '12345',
            }
        ))
        resource = {
            'id': '12345',
            'resourceType': 'Patient',
        }

        case_block = build_case_block(
            self.patient_type,
            resource,
            suggested_case_id,
        )
        self.assertFalse(case_block.create)
        self.assertEqual(case_block.case_id, case_id)
        self.assertEqual(case_block.external_id, '12345')

    def test_resource_has_external_id_in_other_domain(self):
        case_id = str(uuid4())
        suggested_case_id = str(uuid4())

        with other_domain_factory('other-test-domain') as factory:
            factory.create_or_update_case(CaseStructure(
                case_id=case_id,
                attrs={
                    'create': True,
                    'case_type': 'mother',
                    'case_name': 'Alice APPLE',
                    'owner_id': 'b0b',
                    'external_id': '12345',
                }
            ))
            resource = {
                'id': '12345',
                'resourceType': 'Patient',
            }

            case_block = build_case_block(
                self.patient_type,
                resource,
                suggested_case_id,
            )
            self.assertTrue(case_block.create)
            self.assertEqual(case_block.case_id, suggested_case_id)
            self.assertEqual(case_block.external_id, '12345')

    def test_same_external_id_different_case_type(self):
        case_id = str(uuid4())
        suggested_case_id = str(uuid4())

        self.factory.create_or_update_case(CaseStructure(
            case_id=case_id,
            attrs={
                'create': True,
                'case_type': 'visit',
                'case_name': 'ANC1',
                'owner_id': 'b0b',
                'external_id': '12345',
            }
        ))
        resource = {
            'id': '12345',
            'resourceType': 'Patient',
        }

        case_block = build_case_block(
            self.patient_type,
            resource,
            suggested_case_id,
        )
        self.assertTrue(case_block.create)
        self.assertEqual(case_block.case_id, suggested_case_id)

    def test_resource_is_new(self):
        case_id = str(uuid4())
        suggested_case_id = str(uuid4())

        resource = {
            'id': '12345',
            'name': [{
                'given': ['Alice', 'Amelia', 'Anna'],
                'family': 'Apple',
                'text': 'Alice APPLE',
            }],
            'identifier': [{
                'system': SYSTEM_URI_CASE_ID,
                'value': case_id,
            }],
            'telecom': [{
                'system': 'phone',
                'value': '555-1234',
            }],
            'resourceType': 'Patient',
        }
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': '$.name[0].given',
                'case_property': 'case_name',
                'external_data_type': FHIR_DATA_TYPE_LIST_OF_STRING,
                'commcare_data_type': COMMCARE_DATA_TYPE_TEXT,
            }
        )
        FHIRImportResourceProperty.objects.create(
            resource_type=self.patient_type,
            value_source_config={
                'jsonpath': "$.telecom[?system='phone'].value",
                'case_property': 'phone_number',
            }
        )

        case_block = build_case_block(
            self.patient_type,
            resource,
            suggested_case_id,
        )
        self.assertTrue(case_block.create)
        self.assertEqual(case_block.case_id, suggested_case_id)
        self.assertEqual(case_block.external_id, '12345')
        self.assertEqual(case_block.case_name, 'Alice Amelia Anna')
        self.assertEqual(case_block.update, {'phone_number': '555-1234'})


class TestValidateParentRef(TestCaseWithFHIRResources):

    def test_bad_parent_ref(self):
        parent_ref = '12345'
        with self.assertRaises(ConfigurationError):
            validate_parent_ref(parent_ref, self.patient_type)

    def test_none_parent_ref(self):
        parent_ref = None
        with self.assertRaises(ConfigurationError):
            validate_parent_ref(parent_ref, self.patient_type)

    def test_bad_resource_type(self):
        parent_ref = 'Practitioner/67890'
        with self.assertRaises(ConfigurationError):
            validate_parent_ref(parent_ref, self.patient_type)

    def test_list_parent_ref(self):
        parent_ref = ['Practitioner/67890', 'Patient/12345']
        with self.assertRaises(ConfigurationError):
            validate_parent_ref(parent_ref, self.patient_type)

    def test_good_parent_ref(self):
        parent_ref = 'Patient/12345'
        validate_parent_ref(parent_ref, self.patient_type)


class TestCreateParentIndices(TestCaseWithFHIRResources):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.domain_obj.save()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.domain_obj.delete()

    def run(self, result=None):
        mother_kwargs = {
            'external_id': '12345',
            'update': {
                'given_names': 'Alica Amelia',
                'family_name': 'Apple',
                'phone_number': '555-1234',
            },
        }
        with create_case(DOMAIN, 'referral') as referral, \
                create_case(DOMAIN, 'mother', **mother_kwargs) as mother:
            self.referral_case = referral
            self.mother_case = mother
            super().run(result)

    def test_no_child_cases(self):
        child_cases = []
        with patch('corehq.motech.fhir.tasks.submit_case_blocks') as \
                submit_case_blocks:
            create_parent_indices(self.import_config, child_cases)
            submit_case_blocks.assert_not_called()

    def test_parent_case_missing(self):
        parent_ref = 'Patient/67890'
        child_cases = [
            ParentInfo(self.referral_case.case_id, parent_ref, self.patient_type)
        ]
        with self.assertRaises(ConfigurationError):
            create_parent_indices(self.import_config, child_cases)

    def test_submit_case_blocks(self):
        index_xml = (
            '<index>'
            f'<parent case_type="mother">{self.mother_case.case_id}</parent>'
            '</index>'
        )

        child_case_id = self.referral_case.case_id
        parent_ref = 'Patient/12345'
        child_cases = [
            ParentInfo(child_case_id, parent_ref, self.patient_type)
        ]
        with patch('corehq.motech.fhir.tasks.'
                   'submit_case_blocks') as submit_case_blocks:
            create_parent_indices(self.import_config, child_cases)

            ([case_block], domain), kwargs = submit_case_blocks.call_args
            self.assertIn(index_xml, case_block)


@contextmanager
def other_domain_factory(other_domain_name):
    domain_obj = create_domain(other_domain_name)
    factory = CaseFactory(domain=other_domain_name)
    try:
        yield factory
    finally:
        domain_obj.delete()
