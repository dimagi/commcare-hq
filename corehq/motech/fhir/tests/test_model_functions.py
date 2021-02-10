from uuid import uuid4

from django.test import TestCase

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.form_processor.models import CommCareCaseSQL
from corehq.motech.fhir.models import (
    FHIRResourceProperty,
    FHIRResourceType,
    build_fhir_resource,
    get_case_trigger_info,
)

DOMAIN = 'test-domain'


class TestGetCaseTriggerInfo(TestCase):

    def setUp(self):
        self.case_type = CaseType.objects.create(domain=DOMAIN, name='foo')
        for name in ('een', 'twee', 'drie'):
            CaseProperty.objects.create(case_type=self.case_type, name=name)

    def tearDown(self):
        self.case_type.delete()

    def test_case_properties(self):
        case = CommCareCaseSQL(
            case_id=str(uuid4()),
            domain=DOMAIN,
            type='foo',
            name='bar',
            case_json={
                'een': 1, 'twee': 2, 'drie': 3,
                'vier': 4, 'vyf': 5, 'ses': 6,
            }
        )
        info = get_case_trigger_info(case, self.case_type)
        for name in ('een', 'twee', 'drie'):
            self.assertIn(name, info.updates)
        for name in ('vier', 'vyf', 'ses'):
            self.assertNotIn(name, info.updates)


class TestBuildFHIRResource(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.set_up_case_type()
        cls.set_up_resource_type()

    @classmethod
    def set_up_case_type(cls):
        cls.case_type = CaseType.objects.create(domain=DOMAIN, name='mother')

        cls.name = CaseProperty.objects.create(
            case_type=cls.case_type, name='name')
        cls.first_name = CaseProperty.objects.create(
            case_type=cls.case_type, name='first_name')
        cls.honorific = CaseProperty.objects.create(
            case_type=cls.case_type, name='honorific')
        cls.date_of_birth = CaseProperty.objects.create(
            case_type=cls.case_type, name='date_of_birth')

        cls.case = CommCareCaseSQL(
            case_id=str(uuid4()),
            domain=DOMAIN,
            type='mother',
            name='Mehter Plethwih',
            case_json={
                'first_name': 'Plethwih',
                'honorific': 'Mehter',
                'date_of_birth': '1970-01-01',
                'children': ['Hewsos', 'the twins'],
            }
        )

    @classmethod
    def set_up_resource_type(cls):
        resource_type = FHIRResourceType.objects.create(
            case_type=cls.case_type,
            fhirclient_class='UNUSED',
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type,
            case_property=cls.name,
            jsonpath='$.name[0].text',
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type,
            case_property=cls.first_name,
            jsonpath='$.name[0].given[0]',
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type,
            case_property=cls.honorific,
            jsonpath='$.name[0].prefix[0]',
        )
        FHIRResourceProperty.objects.create(
            resource_type=resource_type,
            case_property=cls.date_of_birth,
            jsonpath='$.birthDate',
        )

    @classmethod
    def tearDownClass(cls):
        cls.case_type.delete()
        super().tearDownClass()

    def test_build_fhir_resource(self):
        resource = build_fhir_resource(self.case)
        self.assertEqual(resource, {
            'name': [{
                'text': 'Mehter Plethwih',
                'prefix': ['Mehter'],
                'given': ['Plethwih'],
            }],
            'birthDate': '1970-01-01',
        })

    def test_num_queries(self):
        with self.assertNumQueries(5):
            build_fhir_resource(self.case)
