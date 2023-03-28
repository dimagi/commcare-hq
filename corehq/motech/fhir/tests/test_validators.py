from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from corehq.motech.fhir.models import FHIRResourceType
from corehq.motech.fhir.utils import load_fhir_resource_types

class TestValidateSupportedFHIRTypes(SimpleTestCase):
    def test_valid_fhir_type(self):
        fhir_type = FHIRResourceType()
        fhir_type.name = "Patient"
        try:
            fhir_type.full_clean()
        except ValidationError as e:
            self.assertIsNone(e.message_dict.get('name'))

    def test_invalid_fhir_type(self):
        fhir_type = FHIRResourceType()
        fhir_type.name = "Random"
        supported_resources_types = load_fhir_resource_types()
        try:
            fhir_type.full_clean()
        except ValidationError as e:
            self.assertEqual(
                e.message_dict['name'],
                ['Unsupported FHIR Resource type Random. Please choose from '
                 + ', '.join(supported_resources_types)]
            )
