from django.conf import settings
from django.urls import reverse

from dimagi.utils.web import get_url_base


def get_request_data(request):
    """
    OneLogin's python3-saml library expects a very specifically formatted
    "request_data" object as it is framework agnostic and each framework
    (eg flask, django, tornado) has its own way of populating the built in
    request object
    :param request:
    :return: dictionary with fields that python3-saml expects
    """
    return {
        'https': ('off' if settings.SAML2_DEBUG and not request.is_secure()
                  else 'on'),
        'http_host': request.META['HTTP_HOST'],
        'script_name': request.META['PATH_INFO'],

        # see https://github.com/onelogin/python3-saml/issues/83
        'server_port': (request.META['SERVER_PORT']
                        if settings.SAML2_DEBUG else '443'),

        'get_data': request.GET.copy(),
        'post_data': request.POST.copy(),
    }


def _get_full_sso_url(view_name, identity_provider):
    return "{}{}".format(
        get_url_base(),
        reverse(view_name, args=(identity_provider.slug,))
    )


def get_saml_entity_id(identity_provider):
    return _get_full_sso_url("sso_saml_metadata", identity_provider)


def get_saml_acs_url(identity_provider):
    return _get_full_sso_url("sso_saml_acs", identity_provider)


def get_saml_sls_url(identity_provider):
    return _get_full_sso_url("sso_saml_sls", identity_provider)


def get_dashboard_link(identity_provider):
    from corehq.apps.accounting.models import Subscription
    from corehq.apps.sso.views.enterprise_admin import EditIdentityProviderEnterpriseView
    linked_subscription = Subscription.visible_objects.filter(
        account=identity_provider.owner,
        is_active=True,
        account__is_active=True,
    ).first()
    if linked_subscription:
        return reverse(
            EditIdentityProviderEnterpriseView.urlname,
            args=(linked_subscription.subscriber.domain, identity_provider.slug,)
        )
    # would only ever reach this in tests
    return '#'

