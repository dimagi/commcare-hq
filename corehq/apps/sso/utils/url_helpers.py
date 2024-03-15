from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from django.urls import reverse

from corehq.apps.sso.models import IdentityProvider
from dimagi.utils.web import get_url_base


def get_saml_entity_id(identity_provider):
    return _get_full_sso_url("sso_saml_metadata", identity_provider)


def get_saml_acs_url(identity_provider):
    return _get_full_sso_url("sso_saml_acs", identity_provider)


def get_saml_login_url(identity_provider):
    return _get_full_sso_url("sso_saml_login", identity_provider)


def get_oidc_login_url(identity_provider):
    return _get_full_sso_url("sso_oidc_login", identity_provider)


def get_oidc_auth_url(identity_provider):
    return _get_full_sso_url("sso_oidc_auth", identity_provider)


def get_oidc_logout_url(identity_provider):
    return _get_full_sso_url("sso_oidc_logout", identity_provider)


def get_documentation_url(identity_provider):
    # todo we are only supporting docs for Azure AD here. OneLogin, etc to come later
    return 'https://confluence.dimagi.com/display/commcarepublic/Set+up+SSO+for+CommCare+HQ'


def get_dashboard_link(identity_provider):
    from corehq.apps.accounting.models import Subscription
    from corehq.apps.sso.views.enterprise_admin import EditIdentityProviderEnterpriseView
    linked_subscription = Subscription.visible_objects.filter(
        account=identity_provider.owner,
        is_active=True,
        account__is_active=True,
    ).first()
    try:
        enterprise_domain = linked_subscription.subscriber.domain
    except AttributeError:
        return None
    return reverse(
        EditIdentityProviderEnterpriseView.urlname,
        args=(enterprise_domain, identity_provider.slug,)
    )


def _get_full_sso_url(view_name, identity_provider):
    return "{}{}".format(
        get_url_base(),
        reverse(view_name, args=(identity_provider.slug,))
    )


def add_username_hint_to_login_url(login_url, request):
    username = request.GET.get('username')
    if username:
        # verify that the stored user data actually the current IdP
        idp = IdentityProvider.get_active_identity_provider_by_username(username)
        if idp and idp.slug == request.idp.slug:
            parsed_url = list(urlparse(login_url))
            params = dict(parse_qsl(parsed_url[4]))
            params['login_hint'] = username
            parsed_url[4] = urlencode(params)
            login_url = urlunparse(parsed_url)
    return login_url
