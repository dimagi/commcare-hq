from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

from corehq.apps.sso.models import IdentityProvider, AuthenticatedEmailDomain


class SsoBackend(ModelBackend):
    """
    Authenticates against an IdentityProvider and SAML2 session data.
    """

    def authenticate(self, request, username=None, idp_slug=None, **kwargs):
        #  Note: when implementing ODIC or other protocols in the future,
        #   a different request.session check can be made
        if not (username and idp_slug and request.session.get('samlSessionIndex')):
            return None

        try:
            identity_provider = IdentityProvider.objects.get(slug=idp_slug)
        except IdentityProvider.DoesNotExist:
            # not sure how we would even get here, but just in case
            request.sso_login_error = "Identity Provider does not exist."
            return None

        if not identity_provider.is_active:
            request.sso_login_error = "This Identity Provider is not active."
            return None

        try:
            email_domain = username.split('@', 1)[1]
        except IndexError:
            # not a valid username
            request.sso_login_error = f"Username {username} is not valid."
            return None

        if not AuthenticatedEmailDomain.objects.filter(
            email_domain=email_domain, identity_provider=identity_provider
        ).exists():
            # if this user's email domain is not authorized by this identity
            # do not continue with authentication
            request.sso_login_error = (
                f"The Email Domain {email_domain} is not allowed to "
                f"authenticate with this Identity Provider."
            )
            return None

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # todo handle user creation based on information from request/session
            #  do this prior to handling the invite scenario and new user scenario
            request.sso_login_error = f"User {username} does not exist."
            return None

        request.sso_login_error = None
        # todo what happens with 2FA required here?
        return user
