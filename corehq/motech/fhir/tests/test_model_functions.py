from uuid import uuid4

from django.test import TestCase

from nose.tools import assert_equal

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.form_processor.models import CommCareCaseSQL
from corehq.motech.exceptions import ConfigurationError

from ..const import FHIR_VERSION_4_0_1
from ..models import (
    FHIRResourceProperty,
    FHIRResourceType,
    _build_fhir_resource,
    build_fhir_resource,
    build_fhir_resource_for_info,
    deepmerge,
    get_case_trigger_info,
    get_resource_type_or_none,
)

DOMAIN = 'test-domain'


class TestGetCaseTriggerInfo(TestCase):

    def setUp(self):
        self.case_type = CaseType.objects.create(domain=DOMAIN, name='foo')
        self.resource_type = FHIRResourceType.objects.create(
            domain=DOMAIN,
            case_type=self.case_type,
            name='Foo',
        )
        for name in ('een', 'twee', 'drie'):
            prop = CaseProperty.objects.create(
                case_type=self.case_type,
                name=name,
            )
            FHIRResourceProperty.objects.create(
                resource_type=self.resource_type,
                case_property=prop,
                jsonpath=f'$.{name}',
            )

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
        info = get_case_trigger_info(case, self.resource_type)
        for name in ('een', 'twee', 'drie'):
            self.assertIn(name, info.extra_fields)
        for name in ('vier', 'vyf', 'ses'):
            self.assertNotIn(name, info.extra_fields)


class TestBuildFHIRResource(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_type = CaseType.objects.create(domain=DOMAIN, name='mother')
        cls.resource_type = FHIRResourceType.objects.create(
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
                resource_type=cls.resource_type,
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
        cls.empty_case = CommCareCaseSQL(
            case_id=uuid4().hex,
            domain=DOMAIN,
            type='mother',
            name=None,  # mapped property has no value
            case_json={'last_name': 'Doe'},  # property not mapped
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

    def test_skip_empty(self):
        rt = get_resource_type_or_none(self.empty_case, FHIR_VERSION_4_0_1)
        info = get_case_trigger_info(self.empty_case, rt)
        resource = build_fhir_resource_for_info(info, rt)
        self.assertIsNone(resource)

    def test_raise_on_empty(self):
        with self.assertRaises(ConfigurationError):
            build_fhir_resource(self.empty_case, FHIR_VERSION_4_0_1)

    def test_num_queries(self):
        with self.assertNumQueries(3):
            rt = get_resource_type_or_none(self.case, FHIR_VERSION_4_0_1)
        with self.assertNumQueries(0):
            info = get_case_trigger_info(self.case, rt)
        with self.assertNumQueries(0):
            _build_fhir_resource(info, rt)


def test_deepmerge():
    for a, b, expected in [
        ('foo', 'bar', 'bar'),
        (['foo'], ['bar'], ['bar']),
        ({'foo': 1}, {'bar': 2}, {'foo': 1, 'bar': 2}),
        ([1, 2], [3], [3, 2]),

        ({'foo': [1, 2]}, {'foo': [3]}, {'foo': [3, 2]}),
        ({'foo': (1, 2)}, {'foo': (3,)}, {'foo': (3,)}),
        ({'foo': [1]}, {'foo': [3, 2]}, {'foo': [3, 2]}),

        ({'foo': {'bar': 1}}, {'foo': {'baz': 2}},
         {'foo': {'bar': 1, 'baz': 2}}),

        ({'foo': None}, {'foo': 1}, {'foo': 1}),
        ({'foo': 1}, {'foo': None}, {'foo': 1}),  # Don't replace with None ...
        ({'foo': [1]}, {'foo': [None, None]},  # ... unless it's all you've got
         {'foo': [1, None]}),
    ]:
        yield check_deepmerge, a, b, expected


def check_deepmerge(a, b, expected):
    result = deepmerge(a, b)
    assert_equal(result, expected)
