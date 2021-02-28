from uuid import uuid4

from django.test import TestCase

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.form_processor.models import CommCareCaseSQL
from ..const import FHIR_VERSION_4_0_1
from ..models import (
    FHIRResourceProperty,
    FHIRResourceType,
    _build_fhir_resource,
    get_case_trigger_info,
    build_fhir_resource,
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
        info = get_case_trigger_info(case)
        for name in ('een', 'twee', 'drie'):
            self.assertIn(name, info.extra_fields)
        for name in ('vier', 'vyf', 'ses'):
            self.assertNotIn(name, info.extra_fields)


class TestBuildFHIRResource(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_type = CaseType.objects.create(domain=DOMAIN, name='mother')
        resource_type = FHIRResourceType.objects.create(
            domain=DOMAIN,
            case_type=case_type,
            name='Patient',
        )
        for name, jsonpath in [
            ('name', '$.name[0].text'),
            ('first_name', '$.name[0].given[0]'),
            ('honorific', '$.name[0].prefix[0]'),
            ('date_of_birth', '$.birthDate'),
        ]:
            prop = CaseProperty.objects.create(case_type=case_type, name=name)
            FHIRResourceProperty.objects.create(
                resource_type=resource_type,
                case_property=prop,
                jsonpath=jsonpath,
            )

        cls.case_id = str(uuid4())
        cls.case = CommCareCaseSQL(
            case_id=cls.case_id,
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
    def tearDownClass(cls):
        CaseType.objects.filter(domain=DOMAIN, name='mother').delete()
        super().tearDownClass()

    def test_build_fhir_resource(self):
        resource = build_fhir_resource(self.case)
        self.assertEqual(resource, {
            'id': self.case_id,
            'name': [{
                'text': 'Mehter Plethwih',
                'prefix': ['Mehter'],
                'given': ['Plethwih'],
            }],
            'birthDate': '1970-01-01',
            'resourceType': 'Patient',
        })

    def test_num_queries(self):
        info = get_case_trigger_info(self.case)
        with self.assertNumQueries(3):
            _build_fhir_resource(info, FHIR_VERSION_4_0_1)
