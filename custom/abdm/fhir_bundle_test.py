# 1. Read Composition Definition for a HI Type
# 2. Based on definition, find out entries required for HI Type (manual or read from json def)
# 3. Load all required entries through MOTECH fhir and data dictionary
# 4. Create the Composition Entry
# 5. Create the Bundle with all entries

# Additional: Use fhir client if it makes easier to create bundles and even for parsing purpose

# NOTE: This will be created based on the Project Support as not all are mandatory
# PATIENT will be a Parent Case and rest all resources will be created as child cases
# CareContextReference which will refer to Patient Visit by ANM will be input for us
# If CareContextReference will be child case, then we need to find parent case for that and use that to get all
# associated resources

# This will contain R4 resources
from corehq.motech.fhir.const import FHIR_VERSION_4_0_1
from corehq.motech.fhir.models import FHIRResourceType, build_fhir_resource
from corehq.motech.fhir.utils import load_fhir_resource_types
from corehq.util.view_utils import get_case_or_404
from corehq.motech.exceptions import ConfigurationError

PRESCRIPTION_RESOURCES = ['Patient', 'MedicationRequest']
# Similarly add resource types for other HI Types

ABDM_FHIR_VERSION = FHIR_VERSION_4_0_1

domain = ''
care_context_reference = ''

entries = []
for resource_type in PRESCRIPTION_RESOURCES:
    # TODO Need to find resource id based on care context reference
    resource_id = ''
    case = get_case_or_404(domain, resource_id)
    if not FHIRResourceType.objects.filter(
        domain=domain,
        fhir_version=ABDM_FHIR_VERSION,
        name=resource_type,
        case_type__name=case.type
    ).exists():
        raise Exception("Invalid Resource type")
    try:
        entries.append(build_fhir_resource(case))
    except ConfigurationError:
        raise Exception('FHIR configuration error. Please notify administrator')

# TODO Create Composition Resource
# TODO Create Bundle Document
# TODO Check for FHIR and Data Dict toggle availability

# Questions:
# 1. Which case id do we want for Care Context Reference ? Patient ?

