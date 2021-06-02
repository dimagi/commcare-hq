from django.core.validators import ValidationError
from django.utils.translation import gettext_lazy as _

from corehq.motech.fhir.const import SUPPORTED_FHIR_RESOURCE_TYPES


def validate_supported_type(value):
    if value and value not in SUPPORTED_FHIR_RESOURCE_TYPES:
        raise ValidationError(
            _('Unsupported FHIR Resource type {}. Please choose from {}').format(
                value, ', '.join(SUPPORTED_FHIR_RESOURCE_TYPES))
        )
