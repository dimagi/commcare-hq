import doctest
from contextlib import contextmanager

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from nose.tools import assert_in

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.fhir import models
from corehq.motech.models import ConnectionSettings

from ..const import FHIR_VERSION_4_0_1, IMPORT_FREQUENCY_DAILY
from ..models import (
    FHIRImporter,
    FHIRImporterResourceType,
    FHIRResourceProperty,
    FHIRResourceType,
    JSONPathToResourceType,
)

DOMAIN = 'test-domain'


class TestFHIRImporter(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Test ConnectionSettings',
            url='https://example.com/api/',
        )

    @classmethod
    def tearDownClass(cls):
        cls.conn.delete()
        super().tearDownClass()

    def tearDown(self):
        FHIRImporter.objects.filter(domain=DOMAIN).delete()

    def test_connection_settings_null(self):
        importer = FHIRImporter(
            domain=DOMAIN,
            owner_id='b0b',
        )
        with self.assertRaises(ValidationError):
            importer.full_clean()
        with self.assertRaises(IntegrityError), \
                transaction.atomic():
            importer.save()

    def test_connection_settings_protected(self):
        FHIRImporter.objects.create(
            domain=DOMAIN,
            connection_settings=self.conn,
            owner_id='b0b',
        )
        with self.assertRaises(ProtectedError):
            self.conn.delete()

    def test_fhir_version_good(self):
        importer = FHIRImporter(
            domain=DOMAIN,
            connection_settings=self.conn,
            fhir_version=FHIR_VERSION_4_0_1,
            owner_id='b0b',
        )
        importer.full_clean()

    def test_fhir_version_bad(self):
        importer = FHIRImporter(
            domain=DOMAIN,
            connection_settings=self.conn,
            fhir_version='1.0.2',
            owner_id='b0b',
        )
        with self.assertRaises(ValidationError):
            importer.full_clean()

    def test_frequency_good(self):
        importer = FHIRImporter(
            domain=DOMAIN,
            connection_settings=self.conn,
            frequency=IMPORT_FREQUENCY_DAILY,
            owner_id='b0b',
        )
        importer.full_clean()

    def test_frequency_bad(self):
        importer = FHIRImporter(
            domain=DOMAIN,
            connection_settings=self.conn,
            frequency='weekly',
            owner_id='b0b',
        )
        with self.assertRaises(ValidationError):
            importer.full_clean()

    def test_owner_id_missing(self):
        importer = FHIRImporter(
            domain=DOMAIN,
            connection_settings=self.conn,
        )
        with self.assertRaises(ValidationError):
            importer.full_clean()


class TestFHIRImporterResourceType(TestCase):

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
            owner_id='b0b',
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

    def test_search_params_empty(self):
        service_request = FHIRImporterResourceType.objects.create(
            fhir_importer=self.fhir_importer,
            name='ServiceRequest',
            case_type=self.referral,
        )
        self.assertEqual(service_request.search_params, {})

    def test_related_resource_types(self):
        service_request = FHIRImporterResourceType.objects.create(
            fhir_importer=self.fhir_importer,
            name='ServiceRequest',
            case_type=self.referral,
        )
        patient = FHIRImporterResourceType.objects.create(
            fhir_importer=self.fhir_importer,
            name='Patient',
            case_type=self.mother,
        )
        JSONPathToResourceType.objects.create(
            resource_type=service_request,
            jsonpath='$.subject.reference',
            related_resource_type=patient,
        )

        related = service_request.jsonpaths_to_related_resource_types.all()
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0].related_resource_type.name, 'Patient')
        case_type = related[0].related_resource_type.case_type
        self.assertEqual(case_type.name, 'mother')


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

    def test_resource_type_name(self):
        self.resource_type.name = 'Patinet'
        with self.assertRaisesRegex(
                ConfigurationError,
                "^Unknown resource type 'Patinet' for FHIR version 4.0.1$"
        ):
            self.resource_type.get_json_schema()

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


class TestModelIntegrity(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mother = CaseType.objects.create(
            domain=DOMAIN,
            name='mother',
        )
        cls.patient = models.FHIRResourceType.objects.create(
            domain=DOMAIN,
            case_type=cls.mother,
            name='Patient'
        )

    @classmethod
    def tearDownClass(cls):
        cls.patient.delete()
        cls.mother.delete()
        super().tearDownClass()

    def test_two_resource_types_one_case_type_bad(self):
        """
        Case type "mother" can't be mapped to both "Patient" and "Person"
        """
        with self.assertRaises(IntegrityError):
            models.FHIRResourceType.objects.create(
                domain=DOMAIN,
                case_type=self.mother,
                name='Person'
            )

    def test_two_case_types_one_resource_type_ok(self):
        """
        Case types "mother" and "child" can both be mapped to "Patient"
        """
        child = CaseType.objects.create(
            domain=DOMAIN,
            name='child',
        )
        self.addCleanup(child.delete)

        patient_again = models.FHIRResourceType.objects.create(
            domain=DOMAIN,
            case_type=child,
            name='Patient'
        )
        self.addCleanup(patient_again.delete)


class TestResourceValidation(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type = CaseType.objects.create(
            domain=DOMAIN,
            name='person',
        )
        cls.resource_type = models.FHIRResourceType.objects.create(
            domain=DOMAIN,
            case_type=cls.case_type,
            name='Patient'
        )

    @classmethod
    def tearDownClass(cls):
        cls.resource_type.delete()
        cls.case_type.delete()
        super().tearDownClass()

    def test_minimal(self):
        patient = {'resourceType': 'Patient'}
        self.resource_type.validate_resource(patient)

    def test_required_property(self):
        patient = {}
        with self.assertRaisesRegex(ConfigurationError,
                                    "'resourceType' is a required property"):
            self.resource_type.validate_resource(patient)

    def test_bad_data_type(self):
        patient = {
            'birthDate': 1,
            'resourceType': 'Patient',
        }
        with self.assertRaisesRegex(ConfigurationError,
                                    "1 is not of type 'string'"):
            self.resource_type.validate_resource(patient)

    def test_bad_format(self):
        patient = {
            'birthDate': '05/05/43',
            'resourceType': 'Patient',
        }
        with self.assertRaisesRegex(ConfigurationError,
                                    "'05/05/43' does not match "):
            self.resource_type.validate_resource(patient)

    def test_bad_scalar(self):
        patient = {
            'name': 'Michael Palin',
            'resourceType': 'Patient',
        }
        with self.assertRaisesRegex(ConfigurationError,
                                    "'Michael Palin' is not of type 'array'"):
            self.resource_type.validate_resource(patient)

    def test_bad_vector(self):
        patient = {
            'name': [{'family': ['Palin']}],
            'resourceType': 'Patient'
        }
        with self.assertRaisesRegex(ConfigurationError,
                                    r"\['Palin'\] is not of type 'string'"):
            self.resource_type.validate_resource(patient)


def test_names():
    names = FHIRResourceType.get_names()
    assert_in('Patient', names)


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
