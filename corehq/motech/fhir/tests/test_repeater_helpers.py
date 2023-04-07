import random
import string
from datetime import datetime
from unittest.mock import Mock
from uuid import uuid4

from django.test import TestCase

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DECIMAL,
    COMMCARE_DATA_TYPE_TEXT,
)
from corehq.motech.value_source import CaseTriggerInfo

from ..const import FHIR_DATA_TYPE_LIST_OF_STRING, FHIR_VERSION_4_0_1
from ..models import (
    FHIRResourceProperty,
    FHIRResourceType,
    get_case_trigger_info,
    get_resource_type_or_none,
)
from ..repeater_helpers import get_info_resource_list, send_resources

DOMAIN = ''.join([random.choice(string.ascii_lowercase) for __ in range(20)])


class TestGetInfoResourcesListOneCase(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)

        cls.case_type = CaseType.objects.create(
            domain=DOMAIN, name='person')
        name = CaseProperty.objects.create(
            case_type=cls.case_type, name='name')

        resource_type = FHIRResourceType.objects.create(
            domain=DOMAIN, case_type=cls.case_type, name='Patient')
        FHIRResourceProperty.objects.create(
            resource_type=resource_type,
            case_property=name,
            jsonpath='$.name[0].text',
        )

    @classmethod
    def tearDownClass(cls):
        cls.case_type.delete()
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def setUp(self):
        now = datetime.utcnow()
        self.case_id = str(uuid4())
        self.case = CommCareCase(
            case_id=self.case_id,
            domain=DOMAIN,
            type='person',
            name='Ted',
            owner_id=str(uuid4()),
            modified_on=now,
            server_modified_on=now,
        )
        self.case.save()

    def tearDown(self):
        self.case.delete()

    def test_get_info_resource_list(self):
        resource_type = get_resource_type_or_none(self.case, FHIR_VERSION_4_0_1)
        case_trigger_infos = [get_case_trigger_info(self.case, resource_type)]
        resource_types_by_case_type = {'person': resource_type}
        [(info, resource)] = get_info_resource_list(
            case_trigger_infos,
            resource_types_by_case_type,
        )
        self.assertEqual(resource, {
            'id': self.case_id,
            'name': [{'text': 'Ted'}],
            'resourceType': 'Patient'
        })


class TestGetInfoResourcesListSubCases(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)

        cls.person_case_type = CaseType.objects.create(
            domain=DOMAIN, name='person')
        name = CaseProperty.objects.create(
            case_type=cls.person_case_type, name='name')

        resource_type_for_person = FHIRResourceType.objects.create(
            domain=DOMAIN, case_type=cls.person_case_type, name='Patient')
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_person,
            case_property=name,
            jsonpath='$.name[0].text',
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_person,
            value_source_config={
                'subcase_value_source': {
                    'case_property': 'given_names',
                    # Use counter1 to skip the name set by the parent case
                    'jsonpath': '$.name[{counter1}].given',
                    'commcare_data_type': COMMCARE_DATA_TYPE_TEXT,
                    'external_data_type': FHIR_DATA_TYPE_LIST_OF_STRING,
                },
                'case_types': ['person_name'],
            }
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_person,
            value_source_config={
                'subcase_value_source': {
                    'case_property': 'family_name',
                    'jsonpath': '$.name[{counter1}].family',
                },
                'case_types': ['person_name'],
            }
        )

    @classmethod
    def tearDownClass(cls):
        cls.person_case_type.delete()
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def setUp(self):
        now = datetime.utcnow()
        self.parent_case_id = str(uuid4())
        self.parent_case = CommCareCase(
            case_id=self.parent_case_id,
            domain=DOMAIN,
            type='person',
            name='Ted',
            owner_id=str(uuid4()),
            modified_on=now,
            server_modified_on=now,
        )
        self.parent_case.save()

        self.child_case_1 = CommCareCase(
            case_id='111111111',
            domain=DOMAIN,
            type='person_name',
            name='Theodore',
            case_json={
                'given_names': 'Theodore John',
                'family_name': 'Kaczynski',
            },
            owner_id=str(uuid4()),
            modified_on=now,
            server_modified_on=now,
        )
        self.child_case_1.save()
        add_case_index(
            self.child_case_1,
            identifier='parent',
            referenced_type='person',
            referenced_id=self.parent_case_id,
        )
        self.child_case_2 = CommCareCase(
            case_id='222222222',
            domain=DOMAIN,
            type='person_name',
            name='Unabomber',
            case_json={'given_names': 'Unabomber'},
            owner_id=str(uuid4()),
            modified_on=now,
            server_modified_on=now,
        )
        self.child_case_2.save()
        add_case_index(
            self.child_case_2,
            identifier='parent',
            referenced_type='person',
            referenced_id=self.parent_case_id,
        )

    def tearDown(self):
        self.child_case_1.delete()
        self.child_case_2.delete()
        self.parent_case.delete()

    def test_get_info_resource_list(self):
        rt = get_resource_type_or_none(self.parent_case, FHIR_VERSION_4_0_1)
        case_trigger_infos = [get_case_trigger_info(self.parent_case, rt)]
        resource_types_by_case_type = {'person': rt}
        [(info, resource)] = get_info_resource_list(
            case_trigger_infos,
            resource_types_by_case_type,
        )
        self.assertIn({'text': 'Ted'}, resource['name'])
        self.assertIn(
            {'given': ['Theodore', 'John'], 'family': 'Kaczynski'},
            resource['name'],
        )
        self.assertIn({'given': ['Unabomber']}, resource['name'])


class TestGetInfoResourcesListResources(TestCase, DomainSubscriptionMixin):
    """
    Demonstrates building multiple resources using subcases.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)

        cls.person_case_type = CaseType.objects.create(
            domain=DOMAIN, name='person')
        name = CaseProperty.objects.create(
            case_type=cls.person_case_type, name='name')

        resource_type_for_person = FHIRResourceType.objects.create(
            domain=DOMAIN, case_type=cls.person_case_type, name='Patient')
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_person,
            case_property=name,
            jsonpath='$.name[0].text',
        )

        cls.vitals_case_type = CaseType.objects.create(
            domain=DOMAIN, name='vitals')
        CaseProperty.objects.create(
            case_type=cls.vitals_case_type, name='temperature')

        resource_type_for_vitals = FHIRResourceType.objects.create(
            domain=DOMAIN,
            case_type=cls.vitals_case_type,
            name='Observation',
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_vitals,
            value_source_config={
                'jsonpath': '$.code.coding[0].system',
                'value': 'http://loinc.org',
            }
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_vitals,
            value_source_config={
                'jsonpath': '$.code.coding[0].code',
                'value': '8310-5',
            }
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_vitals,
            value_source_config={
                'jsonpath': '$.code.coding[0].display',
                'value': 'Body temperature',
            }
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_vitals,
            value_source_config={
                'jsonpath': '$.code.text',
                'value': 'Temperature',
            }
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_vitals,
            value_source_config={
                'jsonpath': '$.valueQuantity.unit',
                'value': 'degrees Celsius',
            }
        )

        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_vitals,
            value_source_config={
                'case_property': 'temperature',
                'jsonpath': '$.valueQuantity.value',
                'external_data_type': COMMCARE_DATA_TYPE_DECIMAL,
            }
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_vitals,
            value_source_config={
                'supercase_value_source': {
                    'case_property': 'name',
                    'jsonpath': '$.subject.display',
                }
            }
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type_for_vitals,
            value_source_config={
                'supercase_value_source': {
                    'case_property': 'case_id',
                    'jsonpath': '$.subject.reference',
                }
            }
        )

    @classmethod
    def tearDownClass(cls):
        cls.person_case_type.delete()
        cls.vitals_case_type.delete()
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def setUp(self):
        now = datetime.utcnow()
        owner_id = str(uuid4())
        self.parent_case_id = str(uuid4())
        self.parent_case = CommCareCase(
            case_id=self.parent_case_id,
            domain=DOMAIN,
            type='person',
            name='Beth',
            owner_id=owner_id,
            modified_on=now,
            server_modified_on=now,
        )
        self.parent_case.save()

        self.child_case_id = str(uuid4())
        self.child_case = CommCareCase(
            case_id=self.child_case_id,
            domain=DOMAIN,
            type='vitals',
            case_json={'temperature': 36.1},
            owner_id=owner_id,
            modified_on=now,
            server_modified_on=now,
        )
        self.child_case.save()
        add_case_index(
            self.child_case,
            identifier='parent',
            referenced_type='person',
            referenced_id=self.parent_case_id,
        )

    def tearDown(self):
        self.child_case.delete()
        self.parent_case.delete()

    def test_get_info_resource_list(self):
        resource_type_for_person = get_resource_type_or_none(
            self.parent_case,
            FHIR_VERSION_4_0_1,
        )
        resource_type_for_vitals = get_resource_type_or_none(
            self.child_case,
            FHIR_VERSION_4_0_1,
        )
        case_trigger_infos = [
            get_case_trigger_info(self.parent_case, resource_type_for_person),
            get_case_trigger_info(self.child_case, resource_type_for_vitals),
        ]
        resource_types_by_case_type = {
            'person': resource_type_for_person,
            'vitals': resource_type_for_vitals,
        }
        info_resource_list = get_info_resource_list(
            case_trigger_infos,
            resource_types_by_case_type,
        )
        resources = [resource for info, resource in info_resource_list]
        self.assertEqual(resources, [{
            'id': self.parent_case_id,
            'name': [{'text': 'Beth'}],
            'resourceType': 'Patient',
        }, {
            'id': self.child_case_id,
            'code': {
                'coding': [{
                    'system': 'http://loinc.org',
                    'code': '8310-5',
                    'display': 'Body temperature',
                }],
                'text': 'Temperature',
            },
            'valueQuantity': {
                'value': 36.1,
                'unit': 'degrees Celsius',
            },
            'subject': {
                'reference': self.parent_case_id,
                'display': 'Beth',
            },
            'resourceType': 'Observation',
        }])


class TestWhenToBundle(TestCase):

    def setUp(self):
        self.requests = Mock()

    def test_nothing_to_send(self):
        info_resources_list = []
        response = send_resources(
            self.requests,
            info_resources_list,
            FHIR_VERSION_4_0_1,
            repeater_id='abc123',
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.reason, 'No content')

    def test_one_to_send(self):
        info = CaseTriggerInfo(
            domain=DOMAIN,
            case_id='123abc',
            extra_fields={'external_id': '1000'},
        )
        resource = {'id': '123abc', 'resourceType': 'Patient'}
        info_resources_list = [(info, resource)]
        send_resources(
            self.requests,
            info_resources_list,
            FHIR_VERSION_4_0_1,
            repeater_id='abc123',
        )

        self.requests.put.assert_called_with(
            'Patient/1000',
            json=resource,
            raise_for_status=True,
        )

    def test_many_to_send(self):

        def get_obs(id_):
            info = CaseTriggerInfo(
                domain=DOMAIN,
                case_id=id_,
                extra_fields={'external_id': None},
            )
            resource = {
                'id': id_,
                'code': {'text': 'Temperature'},
                'valueQuantity': {'value': 36.1},
                'resourceType': 'Observation',
            }
            return info, resource

        def post(endpoint, **kwargs):
            return f'POSTed to endpoint {endpoint!r}'

        self.requests.post = post

        info_resources_list = [get_obs(x) for x in 'abc']
        response = send_resources(
            self.requests,
            info_resources_list,
            FHIR_VERSION_4_0_1,
            repeater_id='abc123',
        )

        # Bundles are POSTed to API root
        self.assertEqual(response, "POSTed to endpoint '/'")


def add_case_index(child_case, **props):
    child_case.index_set.add(CommCareCaseIndex(
        case=child_case,
        domain=DOMAIN,
        relationship_id=CommCareCaseIndex.CHILD,
        **props
    ), bulk=False)
