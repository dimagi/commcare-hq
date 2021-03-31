from functools import wraps

from django.http import HttpResponseForbidden

from oauth2_provider.oauth2_backends import get_oauthlib_core


def smart_auth(view):
    """Validates a request against the SMART-on-FHIR OAuth access protocol by
    checking that the scope of the OAuth token is valid for the resource type

    """

    def _build_required_scope(resource_type, request):
        if request.method.upper() in ["GET", "HEAD", "OPTIONS"]:
            read_write_scope = 'read'
        else:
            read_write_scope = 'write'
        # TODO: If this is a WebUser, then allow `patient`
        return [f'user/{resource_type}.{read_write_scope}']

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        core = get_oauthlib_core()
        valid, oauth_request = core.verify_request(
            request, scopes=_build_required_scope(kwargs['resource_type'], request)
        )

        if not valid:
            return HttpResponseForbidden(oauth_request.oauth2_error.get('error_description', ''))
        request.oauth_access_token = oauth_request.access_token

        return view(request, *args, **kwargs)

    return wrapper
