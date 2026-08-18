from django.utils.decorators import method_decorator
from oauth2_provider.views.base import AuthorizationView

from corehq.apps.hqwebapp.decorators import use_bootstrap5


@method_decorator(use_bootstrap5, name="dispatch")
class HQAuthorizationView(AuthorizationView):
    """
    The OAuth2 consent screen, extended with a custom HTML template.
    """
    urlname = 'oauth_authorize'
    template_name = 'hqwebapp/bootstrap5/oauth_authorize.html'
