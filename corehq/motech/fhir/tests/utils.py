from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.motech.fhir.const import FHIR_VERSION_4_0_1
from corehq.motech.fhir.models import FHIRResourceProperty, FHIRResourceType


def add_case_type_with_resource_type(domain, case_type, resource_type):
    case_type_obj = CaseType.objects.create(domain=domain, name=case_type)
    resource_type_obj = FHIRResourceType.objects.create(
        domain=domain,
        fhir_version=FHIR_VERSION_4_0_1,
        name=resource_type,
        case_type=case_type_obj,
    )
    return case_type_obj, resource_type_obj


def add_case_property_with_resource_property_path(case_type, case_property, resource_type, jsonpath):
    case_property_obj = CaseProperty.objects.create(case_type=case_type, name=case_property)
    FHIRResourceProperty.objects.create(
        resource_type=resource_type,
        case_property=case_property_obj,
        jsonpath=jsonpath
    )
