from django.contrib.auth.models import User

from corehq.apps.sso.exceptions import SsoAuthenticationError
from corehq.apps.sso.models import (
    IdentityProvider,
    AuthenticatedEmailDomain,
)


def get_authenticated_sso_user(username, idp_slug):
    try:
        identity_provider = IdentityProvider.objects.get(slug=idp_slug)
    except IdentityProvider.DoesNotExist:
        # not sure how we would even get here, but just in case
        raise SsoAuthenticationError(f"Identity Provider {idp_slug} does not exist.")

    if not identity_provider.is_active:
        raise SsoAuthenticationError(f"This Identity Provider {idp_slug} is not active.")

    try:
        email_domain = username.split('@', 1)[1]
    except IndexError:
        # not a valid username
        raise SsoAuthenticationError(f"Username {username} is not valid.")

    if not AuthenticatedEmailDomain.objects.filter(
        email_domain=email_domain, identity_provider=identity_provider
    ).exists():
        # if this user's email domain is not authorized by this identity
        # do not continue with authentication
        raise SsoAuthenticationError(
            f"The Email Domain {email_domain} is not allowed to "
            f"authenticate with this Identity Provider ({idp_slug})."
        )

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # todo handle user creation based on information from request/session
        #  do this prior to handling the invite scenario and new user scenario
        raise SsoAuthenticationError(f"User {username} does not exist.")

    # todo what happens with 2FA required here?
    return user
