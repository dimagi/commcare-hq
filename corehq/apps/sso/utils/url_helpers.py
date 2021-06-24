from django.urls import reverse

from dimagi.utils.web import get_url_base


def get_saml_entity_id(identity_provider):
    return _get_full_sso_url("sso_saml_metadata", identity_provider)


def get_saml_acs_url(identity_provider):
    return _get_full_sso_url("sso_saml_acs", identity_provider)


def get_saml_login_url(identity_provider):
    return _get_full_sso_url("sso_saml_login", identity_provider)


def get_documentation_url(identity_provider):
    # todo update documentation URL (will change depending on IdP)
    return '#'


def get_dashboard_link(identity_provider):
    from corehq.apps.accounting.models import Subscription
    from corehq.apps.sso.views.enterprise_admin import EditIdentityProviderEnterpriseView
    linked_subscription = Subscription.visible_objects.filter(
        account=identity_provider.owner,
        is_active=True,
        account__is_active=True,
    ).first()
    return reverse(
        EditIdentityProviderEnterpriseView.urlname,
        args=(linked_subscription.subscriber.domain, identity_provider.slug,)
    )


def _get_full_sso_url(view_name, identity_provider):
    return "{}{}".format(
        get_url_base(),
        reverse(view_name, args=(identity_provider.slug,))
    )
