import json

from django.conf import settings
from custom.abdm.fhir.document_bundle import document_bundle_from_hq
from custom.abdm.utils import json_from_file


def get_fhir_data_care_context(care_context_reference):
    # TODO FIGURE out how to do this For package purpose, this will raise NotImplementedError
    # TODO Health information type from care context reference
    # TODO Error handling
    from custom.abdm.const import HealthInformationType
    health_information_type = HealthInformationType.PRESCRIPTION
    # return document_bundle_from_hq(care_context_reference, health_information_type)
    if care_context_reference in ("CC-101"):
        return json_from_file(settings.SAMPLE_FHIR_BUNDLES[0])
    else:
        return json_from_file(settings.SAMPLE_FHIR_BUNDLES[1])
