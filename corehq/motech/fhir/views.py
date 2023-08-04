from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

from corehq import toggles
from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.domain.decorators import (
    login_or_api_key,
    require_superuser,
)
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.fhir.utils import validate_accept_header_and_format_param
from corehq.motech.repeaters.views import AddRepeaterView, EditRepeaterView
from corehq.util.view_utils import get_case_or_404

from .const import FHIR_VERSIONS
from .forms import FHIRRepeaterForm
from .models import FHIRResourceType, build_fhir_resource
from .utils import resource_url


class AddFHIRRepeaterView(AddRepeaterView):
    urlname = 'add_fhir_repeater'
    repeater_form_class = FHIRRepeaterForm
    page_title = _('Forward Cases to a FHIR API')
    page_name = _('Forward Cases to a FHIR API')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super().set_repeater_attr(repeater, cleaned_data)
        for attr in (
            'fhir_version',
            'patient_registration_enabled',
            'patient_search_enabled',
        ):
            value = self.add_repeater_form.cleaned_data[attr]
            setattr(repeater, attr, value)
        return repeater


class EditFHIRRepeaterView(EditRepeaterView, AddFHIRRepeaterView):
    urlname = 'edit_fhir_repeater'
    page_title = _('Edit FHIR Repeater')


@require_GET
@login_or_api_key
@require_superuser
@toggles.FHIR_INTEGRATION.required_decorator()
@validate_accept_header_and_format_param
def get_view(request, domain, fhir_version_name, resource_type, resource_id):
    fhir_version = _get_fhir_version(fhir_version_name)
    if not fhir_version:
        return JsonResponse(status=400, data={'message': "Unsupported FHIR version"})
    case = get_case_or_404(domain, resource_id)

    if not FHIRResourceType.objects.filter(
            domain=domain,
            fhir_version=fhir_version,
            name=resource_type,
            case_type__name=case.type
    ).exists():
        return JsonResponse(status=400, data={'message': "Invalid Resource Type"})
    try:
        resource = build_fhir_resource(case)
    except ConfigurationError:
        return JsonResponse(status=500, data={
            'message': 'FHIR configuration error. Please notify administrator.'
        })
    return JsonResponse(resource)


@require_GET
@login_or_api_key
@require_superuser
@toggles.FHIR_INTEGRATION.required_decorator()
@validate_accept_header_and_format_param
def search_view(request, domain, fhir_version_name, resource_type=None):
    fhir_version = _get_fhir_version(fhir_version_name)
    if not fhir_version:
        return JsonResponse(status=400, data={'message': "Unsupported FHIR version"})
    resource_id = request.GET.get('_id', None) or request.GET.get('patient_id')
    if not resource_id:
        return JsonResponse(status=400, data={'message': "Please pass resource ID."})
    try:
        found_case = CommCareCase.objects.get_case(resource_id, domain)
        if found_case.is_deleted:
            return JsonResponse(status=410, data={'message': "Gone"})
    except CaseNotFound:
        return JsonResponse(status=404, data={'message': "Not Found"})

    resource_types = None
    if resource_type:
        resource_types = [resource_type]
    else:
        type_param = request.GET.get('_type')
        resource_types = [resource_type.strip() for resource_type in type_param.split(',')] if type_param else None

    if not resource_types:
        return JsonResponse(status=400,
                            data={'message': "No resource type specified for search."})
    case_types_for_resource_types = list(
        FHIRResourceType.objects.filter(
            domain=domain, name__in=resource_types, fhir_version=fhir_version
        ).values_list('case_type__name', flat=True)
    )
    if not case_types_for_resource_types:
        return JsonResponse(status=400,
                            data={'message':
                                  f"Resource type(s) {', '.join(resource_types)} not available on {domain}"})

    cases = CommCareCase.objects.get_reverse_indexed_cases(
        domain, [resource_id], case_types=case_types_for_resource_types, is_closed=False)
    if found_case.type in case_types_for_resource_types:
        cases.append(found_case)
    response = {
        'resourceType': "Bundle",
        "type": "searchset",
        "entry": []
    }
    for case in cases:
        case_resource_type = FHIRResourceType.objects.get(
            case_type=CaseType.objects.get(domain=domain, name=case.type))
        response["entry"].append({
            "fullUrl": resource_url(domain, fhir_version_name, case_resource_type, case.case_id),
            "search": {
                "mode": "match"
            }
        })
    return JsonResponse(response)


def _get_fhir_version(fhir_version_name):
    fhir_version = None
    try:
        fhir_version = [v[0] for v in FHIR_VERSIONS if v[1] == fhir_version_name][0]
    except IndexError:
        pass
    return fhir_version
