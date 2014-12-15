from django.conf import settings
from django.core.urlresolvers import resolve, reverse
from django.http import Http404
from django.utils.translation import ugettext as _
from corehq.apps.accounting.utils import domain_has_privilege
from corehq import privileges

from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static

COMMCARE = 'commcare'

COMMCONNECT = 'commconnect'

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
    }


def is_commtrack(project, request):
    if project:
        return project.commtrack_enabled
    try:
        return 'commtrack.org' in request.get_host()
    except Exception:
        # get_host might fail for bad requests, e.g. scheduled reports
        return False


def is_commconnect(project):
    return project and project.commconnect_enabled


def get_domain_type(project, request):
    if is_commtrack(project, request):
        return COMMTRACK
    elif is_commconnect(project):
        return COMMCONNECT
    else:
        return COMMCARE


def get_per_domain_context(project, request=None):
    domain_type = get_domain_type(project, request)
    if domain_type == COMMTRACK:
        logo_url = static('hqstyle/img/commtrack-logo.png')
        site_name = "CommTrack"
        public_site = "http://www.commtrack.org"
        can_be_your = _("mobile logistics solution")
    elif domain_type == COMMCONNECT:
        domain_type = 'commconnect'
        logo_url = static('hqstyle/img/commconnect-logo.png')
        site_name = "CommConnect"
        public_site = "http://www.commcarehq.org"
        can_be_your = _("mobile solution for your frontline workforce")
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
    return settings.ANALYTICS_IDS

def raven(request):
    """lets you know whether raven is being used"""
    return {
        'RAVEN': RAVEN
    }
