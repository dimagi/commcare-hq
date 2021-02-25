from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from corehq import toggles
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    require_superuser,
)
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.repeaters.views import AddRepeaterView, EditRepeaterView

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


@login_and_domain_required
@require_superuser
@toggles.FHIR_INTEGRATION.required_decorator()
def get_view(request, domain, resource_type, resource_id):
    try:
        case = CaseAccessors(domain).get_case(resource_id)
        if case.is_deleted:
            return JsonResponse(status=400, data={'message': f"Resource with ID {resource_id} was removed"})
    except CaseNotFound:
        return JsonResponse(status=400, data={'message': f"Could not find resource with ID {resource_id}"})

    if case.type not in (FHIRResourceType.objects.filter(domain=domain, name=resource_type).
                         values_list('case_type__name', flat=True)):
        return JsonResponse(status=400, data={'message': "Invalid Resource Type"})
    response = {
        'resourceType': resource_type,
        'id': resource_id
    }
    response.update(build_fhir_resource(case))
    return JsonResponse(response)
