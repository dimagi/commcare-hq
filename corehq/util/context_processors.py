import datetime
from django.conf import settings
from django.core.urlresolvers import resolve, reverse
from django.http import Http404
from django.utils.translation import ugettext as _
from corehq.apps.accounting.utils import domain_has_privilege
from corehq import privileges

from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static

RAVEN = bool(getattr(settings, 'SENTRY_DSN', None))

def base_template(request):
    """This sticks the base_template variable defined in the settings
       into the request context."""
    return {
        'base_template': settings.BASE_TEMPLATE,
        'login_template': settings.LOGIN_TEMPLATE,
        'less_debug': settings.LESS_DEBUG,
    }


def get_per_domain_context(project, request=None):
    if project and project.commtrack_enabled:
        domain_type = 'commtrack'
        logo_url = static('hqstyle/img/commtrack-logo.png')
        site_name = "CommTrack"
        public_site = "http://www.commtrack.org"
        can_be_your = _("mobile logistics solution")
    elif project and project.commconnect_enabled:
        domain_type = 'commconnect'
        logo_url = static('hqstyle/img/commconnect-logo.png')
        site_name = "CommConnect"
        public_site = "http://www.commcarehq.org"
        can_be_your = _("mobile solution for your frontline workforce")
    else:
        domain_type = 'commcare'
        logo_url = static('hqstyle/img/commcare-logo.png')
        site_name = "CommCare HQ"
        public_site = "http://www.commcarehq.org"
        can_be_your = _("mobile solution for your frontline workforce")

    try:
        if 'commtrack.org' in request.get_host():
            logo_url = static('hqstyle/img/commtrack-logo.png')
    except Exception:
        # get_host might fail for bad requests, e.g. scheduled reports
        pass

    if (project and project.has_custom_logo
        and domain_has_privilege(project.name, privileges.CUSTOM_BRANDING)
    ):
        logo_url = reverse('logo', args=[project.name])

    return {
        'DOMAIN_TYPE': domain_type,
        'LOGO_URL': logo_url,
        'SITE_NAME': site_name,
        'CAN_BE_YOUR': can_be_your,
        'PUBLIC_SITE': public_site,
    }


def domain(request):
    """Global per-domain context variables"""

    project = getattr(request, 'project', None)
    return get_per_domain_context(project, request=request)


def current_url_name(request):
    """
    Adds the name for the matched url pattern for the current request to the
    request context.
    
    """
    try:
        match = resolve(request.path)
        url_name = match.url_name
    except Http404:
        url_name = None
    
    return {
        'current_url_name': url_name
    }


def analytics_js(request):
    return settings.ANALYTICS_IDS

def raven(request):
    """lets you know whether raven is being used"""
    return {
        'RAVEN': RAVEN
    }


def accounting(request):
    """"""
    billing_notify_contact_missing = False
    update_contact_url = None
    if (hasattr(request, 'subscription')
        and request.subscription is not None
    ):
        from corehq.apps.accounting.models import BillingContactInfo
        try:
            contact_info = request.subscription.account.billingcontactinfo
            contact_missing = contact_info.emails is None
        except BillingContactInfo.DoesNotExist:
            contact_missing = True
        if contact_missing:
            from corehq.apps.domain.views import EditExistingBillingAccountView
            update_contact_url = reverse(
                EditExistingBillingAccountView.urlname,
                args=[request.subscription.subscriber.domain]
            )
            billing_notify_contact_missing = (
                hasattr(request, 'couch_user')
                and request.couch_user.is_domain_admin()
                and request.subscription.subscriber.subscription_set.filter(
                    is_trial=False).count() > 0
                and not request.META['PATH_INFO'].startswith(update_contact_url)
            )
    return {
        'billing_notify_contact_missing': billing_notify_contact_missing,
        'billing_update_contact_url': update_contact_url,
    }
