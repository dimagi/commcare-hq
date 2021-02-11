import doctest
from contextlib import contextmanager

from django.test import TestCase

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.fhir import models
from corehq.motech.fhir.models import FHIRResourceProperty

DOMAIN = 'test-domain'


class TestConfigurationErrors(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type = CaseType.objects.create(
            domain=DOMAIN,
            name='person',
        )
        cls.case_property = CaseProperty.objects.create(
            case_type=cls.case_type,
            name='name',
        )
        cls.resource_type = models.FHIRResourceType.objects.create(
            domain=DOMAIN,
            case_type=cls.case_type,
        )

    @classmethod
    def tearDownClass(cls):
        cls.resource_type.delete()
        cls.case_property.delete()
        cls.case_type.delete()
        super().tearDownClass()

    def setUp(self):
        self.resource_type.name = 'Patient'

    def test_case_types_dont_match(self):
        with case_type_context('child') as child:
            with case_property_context(child, 'name') as child_name:
                prop = FHIRResourceProperty(
                    resource_type=self.resource_type,
                    case_property=child_name,
                    jsonpath='name[0].text',
                )
                with self.assertRaisesRegex(
                        ConfigurationError,
                        "^Invalid FHIRResourceProperty: case_property case "
                        "type 'child' does not match resource_type case type "
                        "'person'.$"
                ):
                    prop.save()

    def test_value_source_config(self):
        prop = FHIRResourceProperty(
            resource_type=self.resource_type,
            case_property=self.case_property,
            jsonpath='name[0].text',
            value_source_config={
                'case_property': 'name',
                'jsonpath': 'name[0].text',
            }
        )
        with self.assertRaisesRegex(
                ConfigurationError,
                "^Invalid FHIRResourceProperty: Unable to set "
                "'value_source_config' when 'case_property', 'jsonpath' or "
                "'value_map' are set.$"
        ):
            prop.save()

    def test_no_jsonpath(self):
        prop = FHIRResourceProperty(
            resource_type=self.resource_type,
            case_property=self.case_property,
        )
        with self.assertRaisesRegex(
                ConfigurationError,
                '^Unable to set FHIR resource property value without case '
                'property and JSONPath.$'
        ):
            prop.get_value_source()

    def test_ok(self):
        prop = FHIRResourceProperty(
            resource_type=self.resource_type,
            case_property=self.case_property,
            jsonpath='name[0].text',
        )
        prop.save()
        self.assertIsNotNone(prop.id)
        value_source = prop.get_value_source()
        self.assertEqual(value_source.__class__.__name__, 'CaseProperty')
        self.assertEqual(value_source.case_property, 'name')
        self.assertEqual(value_source.jsonpath, 'name[0].text')


def test_doctests():
    results = doctest.testmod(models, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0


@contextmanager
def case_type_context(name):
    case_type = CaseType.objects.create(
        domain=DOMAIN,
        name=name,
    )
    try:
        yield case_type
    finally:
        case_type.delete()


@contextmanager
def case_property_context(case_type, name):
    case_property = CaseProperty.objects.create(
        case_type=case_type,
        name=name,
    )
    try:
        yield case_property
    finally:
        case_property.delete()
