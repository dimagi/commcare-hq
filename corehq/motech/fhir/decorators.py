from functools import wraps

from django.http import HttpResponseBadRequest, HttpResponseForbidden

from oauth2_provider.oauth2_backends import get_oauthlib_core

from corehq.apps.consumer_user.models import CaseRelationshipOauthToken


def smart_auth(view):
    """Validates a request for a patient against the SMART-on-FHIR OAuth access protocol.
    It checks that the scope of the OAuth token is valid for the resource type, then validates that
    the user is authorized to access the requested resource

    """

    def _build_required_scope(resource_type, request):
        if request.method.upper() in ["GET", "HEAD", "OPTIONS"]:
            read_write_scope = 'read'
        else:
            read_write_scope = 'write'
        return [f'user/{resource_type}.{read_write_scope}']

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        core = get_oauthlib_core()
        valid, r = core.verify_request(request, scopes=_build_required_scope(kwargs['resource_type'], request))

        if not valid:
            return HttpResponseForbidden(r.oauth2_error.get('error_description', ''))

        try:
            # If this is directly accessing a case
            case_id = kwargs['resource_id']
        except KeyError:
            # If this is accessing a different case based on a patient
            case_id = request.GET.get('patient_id')
        if not case_id:
            return HttpResponseBadRequest("A patient ID is required")

        try:
            # TODO: Check if this is a descendent case
            CaseRelationshipOauthToken.objects.get(
                access_token=r.access_token, consumer_user_case_relationship__case_id=case_id
            )
        except CaseRelationshipOauthToken.DoesNotExist:
            return HttpResponseForbidden("You do not have access to that patient")

        return view(request, *args, **kwargs)

    return wrapper
