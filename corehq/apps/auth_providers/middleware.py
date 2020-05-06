from django.utils.deprecation import MiddlewareMixin

from corehq.apps.auth_providers.utils import SessionAuthManager


class SessionAuthManagerMiddleware(MiddlewareMixin):
    """
    Provides an entry point for multi-backend auth checks

    Log in:
        request.auth_manager.authenticate(COMMCARE_DEFAULT_AUTH)
    Check auth (in a decorator, say):
        auth_accepted_for_user_in_domain = {COMMCARE_DEFAULT_AUTH}
        request.auth_manager.has_auth(auth_accepted_for_user_in_domain):
    Log out:
        request.auth_manager.revoke_auth(COMMCARE_DEFAULT_AUTH)

    """
    def process_request(self, request):
        request.auth_manager = SessionAuthManager(request)
