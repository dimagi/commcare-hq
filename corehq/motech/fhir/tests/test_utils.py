from django.test import TestCase

from nose.tools import assert_equal

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.motech.fhir.models import FHIRResourceProperty, FHIRResourceType
from corehq.motech.fhir.utils import (
    resource_url,
    update_fhir_resource_property,
)

DOMAIN = "test-domain"


class TestUpdateFHIRResourceProperty(TestCase):
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
        cls.resource_type = FHIRResourceType.objects.create(
            domain=DOMAIN,
            case_type=cls.case_type,
        )

    @classmethod
    def tearDownClass(cls):
        cls.resource_type.delete()
        cls.case_property.delete()
        cls.case_type.delete()
        super().tearDownClass()

    def test_delete_if_deprecated(self):
        old_deprecated_value = self.case_property.deprecated
        self.case_property.deprecated = True
        fhir_resource_prop_path = "$.name[0].text"

        # when no resource property mapped
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)
        update_fhir_resource_property(self.case_property, self.resource_type, fhir_resource_prop_path)

        # when resource property present
        fhir_resource_prop = FHIRResourceProperty.objects.create(
            resource_type=self.resource_type,
            case_property=self.case_property,
            jsonpath=fhir_resource_prop_path
        )
        self.addCleanup(fhir_resource_prop.delete)

        update_fhir_resource_property(self.case_property, self.resource_type, fhir_resource_prop_path)
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)

        # reset
        self.case_property.deprecated = old_deprecated_value

    def test_delete_if_to_be_removed(self):
        fhir_resource_prop_path = "$.name[0].text"

        # when no resource property mapped
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)
        update_fhir_resource_property(self.case_property, self.resource_type, fhir_resource_prop_path, True)

        # when resource property present
        fhir_resource_prop = FHIRResourceProperty.objects.create(
            resource_type=self.resource_type,
            case_property=self.case_property,
            jsonpath=fhir_resource_prop_path
        )
        self.addCleanup(fhir_resource_prop.delete)

        update_fhir_resource_property(self.case_property, self.resource_type, fhir_resource_prop_path, True)
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)

    def test_simply_update(self):
        fhir_resource_prop_path = "$.name[0].text"

        # when no resource property mapped
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)
        update_fhir_resource_property(self.case_property, self.resource_type, fhir_resource_prop_path)
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            1)

        # when resource property present
        new_fhir_resource_prop_path = "$.age[0].text"
        update_fhir_resource_property(self.case_property, self.resource_type, new_fhir_resource_prop_path)
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=fhir_resource_prop_path
            ).count(),
            0)
        self.assertEqual(
            FHIRResourceProperty.objects.filter(
                resource_type=self.resource_type,
                case_property=self.case_property,
                jsonpath=new_fhir_resource_prop_path
            ).count(),
            1)


def test_resource_url():
    url = resource_url(DOMAIN, 'R4', 'Patient', 'abc123')
    drop_hostname = url.split('/', maxsplit=3)[3]
    assert_equal(drop_hostname, f'a/{DOMAIN}/fhir/R4/Patient/abc123/')
