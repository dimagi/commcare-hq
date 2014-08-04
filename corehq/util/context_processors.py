import datetime
from django.conf import settings
from django.core.urlresolvers import resolve, reverse
from django.http import Http404
from django.utils.translation import ugettext as _
from corehq.apps.accounting.utils import domain_has_privilege
from corehq import privileges

from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static

COMMCARE = 'commcare'

COMMTRACK = 'commtrack'

RAVEN = bool(getattr(settings, 'SENTRY_DSN', None))


def base_template(request):
    """This sticks the base_template variable defined in the settings
       into the request context."""
    return {
        'base_template': settings.BASE_TEMPLATE,
        'login_template': settings.LOGIN_TEMPLATE,
        'less_debug': settings.LESS_DEBUG,
        'less_watch': settings.LESS_WATCH,
        'use_knockout_js': (request.use_knockout_js
                            if hasattr(request, 'use_knockout_js') else False),
    }


def is_commtrack(project, request):
    if project:
        return project.commtrack_enabled
    try:
        return 'commtrack.org' in request.get_host()
    except Exception:
        # get_host might fail for bad requests, e.g. scheduled reports
        return False


def get_domain_type(project, request):
    if is_commtrack(project, request):
        return COMMTRACK
    else:
        return COMMCARE


def get_per_domain_context(project, request=None):
    domain_type = get_domain_type(project, request)
    if domain_type == COMMTRACK:
        logo_url = static('hqstyle/img/commtrack-logo.png')
        site_name = "CommCare Supply"
        public_site = "http://www.commtrack.org"
        can_be_your = _("mobile logistics solution")
    else:
        logo_url = static('hqstyle/img/commcare-logo.png')
        site_name = "CommCare HQ"
        public_site = "http://www.commcarehq.org"
        can_be_your = _("mobile solution for your frontline workforce")

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
    d = {}
    d.update(settings.ANALYTICS_IDS)
    d.update({"ANALYTICS_CONFIG": settings.ANALYTICS_CONFIG})
    return d

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
