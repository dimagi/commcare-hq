from django.core.validators import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_supported_type(value):
    from corehq.motech.fhir.utils import load_fhir_resource_types
    supported_resources_types = load_fhir_resource_types()
    if value and value not in supported_resources_types:
        raise ValidationError(
            _('Unsupported FHIR Resource type {}. Please choose from {}').format(
                value, ', '.join(supported_resources_types))
        )
