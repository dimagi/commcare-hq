from django.http import JsonResponse

from corehq import toggles
from corehq.apps.domain.decorators import require_superuser, login_and_domain_required
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.fhir.models import FHIRResourceType, build_fhir_resource


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
