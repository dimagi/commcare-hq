from corehq.motech.fhir.models import FHIRResourceProperty, FHIRResourceType
from corehq.util.view_utils import absolute_reverse


def resource_url(domain, fhir_version_name, resource_type, case_id):
    from corehq.motech.fhir.views import get_view
    return absolute_reverse(get_view, args=(domain, fhir_version_name, resource_type, case_id))


def load_fhir_resource_mappings(domain):
    fhir_resource_types = FHIRResourceType.objects.select_related('case_type').filter(domain=domain)
    fhir_resource_type_name_by_case_type = {
        ft.case_type: ft.name
        for ft in fhir_resource_types
    }
    fhir_resource_prop_by_case_prop = {
        fr.case_property: fr.jsonpath
        for fr in FHIRResourceProperty.objects.select_related('case_property').filter(
            resource_type__in=fhir_resource_types)
    }
    return fhir_resource_type_name_by_case_type, fhir_resource_prop_by_case_prop


def update_fhir_resource_type(domain, case_type, fhir_resource_type):
    try:
        fhir_resource_type_obj = FHIRResourceType.objects.get(case_type=case_type, domain=domain)
    except FHIRResourceType.DoesNotExist:
        fhir_resource_type_obj = FHIRResourceType(case_type=case_type, domain=domain)
    fhir_resource_type_obj.name = fhir_resource_type
    fhir_resource_type_obj.full_clean()
    fhir_resource_type_obj.save()
    return fhir_resource_type_obj


def remove_fhir_resource_type(domain, case_type):
    FHIRResourceType.objects.filter(case_type__name=case_type, domain=domain).delete()


def update_fhir_resource_property(case_property, fhir_resource_type, fhir_resource_prop_path, remove_path=False):
    if case_property.deprecated or remove_path:
        try:
            FHIRResourceProperty.objects.get(case_property=case_property,
                                             resource_type=fhir_resource_type,
                                             jsonpath=fhir_resource_prop_path).delete()
        except FHIRResourceProperty.DoesNotExist:
            pass
    elif fhir_resource_prop_path:
        try:
            fhir_resource_prop = FHIRResourceProperty.objects.get(case_property=case_property,
                                                                  resource_type=fhir_resource_type)
        except FHIRResourceProperty.DoesNotExist:
            fhir_resource_prop = FHIRResourceProperty(case_property=case_property,
                                                      resource_type=fhir_resource_type)
        fhir_resource_prop.jsonpath = fhir_resource_prop_path
        fhir_resource_prop.save()
