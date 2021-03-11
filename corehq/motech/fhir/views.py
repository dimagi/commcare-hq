from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_GET

from corehq import toggles
from corehq.apps.domain.decorators import (
    login_or_api_key,
    require_superuser,
)
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.repeaters.views import AddRepeaterView, EditRepeaterView
from corehq.util.view_utils import absolute_reverse, get_case_or_404

from .const import FHIR_VERSIONS
from .forms import FHIRRepeaterForm
from .models import FHIRResourceType, build_fhir_resource


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
        repeater.fhir_version = (self.add_repeater_form
                                 .cleaned_data['fhir_version'])
        return repeater


class EditFHIRRepeaterView(EditRepeaterView, AddFHIRRepeaterView):
    urlname = 'edit_fhir_repeater'
    page_title = _('Edit FHIR Repeater')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])


@require_GET
@login_or_api_key
@require_superuser
@toggles.FHIR_INTEGRATION.required_decorator()
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
    response = {
        'resourceType': resource_type,
        'id': resource_id
    }
    response.update(build_fhir_resource(case))
    return JsonResponse(response)


@require_GET
@login_or_api_key
@require_superuser
@toggles.FHIR_INTEGRATION.required_decorator()
def search_view(request, domain, fhir_version_name, resource_type):
    fhir_version = _get_fhir_version(fhir_version_name)
    if not fhir_version:
        return JsonResponse(status=400, data={'message': "Unsupported FHIR version"})
    patient_case_id = request.GET.get('patient_id')
    if not patient_case_id:
        return JsonResponse(status=400, data={'message': "Please pass patient_id"})
    case_accessor = CaseAccessors(domain)
    try:
        patient_case = case_accessor.get_case(patient_case_id)
        if patient_case.is_deleted:
            return JsonResponse(status=400, data={'message': f"Patient with ID {patient_case_id} was removed"})
    except CaseNotFound:
        return JsonResponse(status=400, data={'message': f"Could not find patient with ID {patient_case_id}"})

    case_types_for_resource_type = list(
        FHIRResourceType.objects.filter(
            domain=domain, name=resource_type, fhir_version=fhir_version
        ).values_list('case_type__name', flat=True)
    )
    if not case_types_for_resource_type:
        return JsonResponse(status=400,
                            data={'message': f"Resource type {resource_type} not available on {domain}"})

    cases = case_accessor.get_reverse_indexed_cases([patient_case_id],
                                                    case_types=case_types_for_resource_type, is_closed=False)
    response = {
        'resourceType': "Bundle",
        "type": "searchset",
        "entry": []
    }
    for case in cases:
        response["entry"].append({
            "fullUrl": absolute_reverse(get_view, args=(domain, resource_type, case.case_id)),
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
