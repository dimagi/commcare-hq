from functools import wraps

from django.http import HttpResponseForbidden
from django.utils.translation import ugettext_lazy as _

from oauth2_provider.oauth2_backends import get_oauthlib_core


def smart_auth(view):
    """Validates a request against the SMART-on-FHIR OAuth access protocol by
    checking that the scope of the OAuth token is valid for the resource type
    """

    def _build_required_scope(resource_type, action):
        # We currently only allow user scopes. When we have provider auth,
        # we can update this to allow `patient/` scopes too
        return [f'user/{resource_type}.{action}']

    def _get_action_from_method(request):
        if request.method.upper() in ["GET", "HEAD", "OPTIONS"]:
            return 'read'
        else:
            return 'write'

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        core = get_oauthlib_core()

        # Oauthlib doesn't have a way to provide a list of optional scopes,
        # So we check each valid scope for this resource in turn
        for resource_type in [kwargs['resource_type'], '*']:
            for action in [_get_action_from_method(request), '*']:
                valid, oauth_request = core.verify_request(
                    request, scopes=_build_required_scope(resource_type, action)
                )
                if valid:
                    break
            if valid:
                break

        if not valid:
            error_message = _("Invalid OAuth Token")
            oauth2_error = getattr(oauth_request, 'oauth2_error', None)
            if oauth2_error:
                error_message = oauth2_error.get('error_description', error_message)
            return HttpResponseForbidden(error_message)
        request.oauth_access_token = oauth_request.access_token

        return view(request, *args, **kwargs)

    return wrapper
