import os
from functools import wraps
from memoized import memoized

from corehq.motech.fhir.const import FHIR_VERSION_4_0_1, HQ_ACCEPTABLE_FHIR_MIME_TYPES
from corehq.motech.fhir.models import (
    FHIRResourceProperty,
    FHIRResourceType,
    get_schema_dir,
)
from corehq.util.view_utils import absolute_reverse

from django.http import JsonResponse


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


@memoized
def load_fhir_resource_types(fhir_version=FHIR_VERSION_4_0_1, exclude_resource_types=('fhir',)):
    schemas_base_path = get_schema_dir(fhir_version)
    all_file_names = os.listdir(schemas_base_path)
    resource_types = [file_name.removesuffix('.schema.json') for file_name in all_file_names
                      if file_name.endswith('.schema.json')]
    for schema in exclude_resource_types:
        if schema in resource_types:
            resource_types.remove(schema)
    resource_types.sort()
    return resource_types


def validate_accept_header_and_format_param(view_func):
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        def _get_format_param(request):
            if request.META.get('REQUEST_METHOD') == 'POST':
                return request.POST.get('_format')
            elif request.META.get('REQUEST_METHOD') == 'GET':
                return request.GET.get('_format')
            else:
                return None
        _format_param = _get_format_param(request)
        if _format_param and _format_param not in HQ_ACCEPTABLE_FHIR_MIME_TYPES + ['json']:
            return JsonResponse(status=406,
                                data={'message': "Requested format in '_format' param not acceptable."})
        else:
            accept_header = request.META.get('HTTP_ACCEPT')
            if accept_header and accept_header not in HQ_ACCEPTABLE_FHIR_MIME_TYPES + ['*/*']:
                return JsonResponse(status=406, data={'message': "Not Acceptable"})
        return view_func(request, *args, **kwargs)

    return _inner


def require_fhir_json_content_type_headers(view_func):
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        if request.content_type not in HQ_ACCEPTABLE_FHIR_MIME_TYPES:
            return JsonResponse(status=415, data={'message': "Unsupported Media Type"})
        return view_func(request, *args, **kwargs)

    return _inner
