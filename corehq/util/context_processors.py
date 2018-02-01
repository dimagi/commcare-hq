from __future__ import absolute_import
from django.conf import settings
from django.urls import resolve, reverse
from django.http import Http404
from ws4redis.context_processors import default
from corehq.apps.accounting.utils import domain_has_privilege
from corehq import privileges
from corehq.apps.hqwebapp.utils import get_environment_friendly_name


COMMCARE = 'commcare'
COMMTRACK = 'commtrack'


def base_template(request):
    """This sticks the base_template variable defined in the settings
       into the request context."""
    return {
        'base_template': settings.BASE_TEMPLATE,
        'login_template': settings.LOGIN_TEMPLATE,
        'less_debug': settings.LESS_DEBUG,
        'env': get_environment_friendly_name(),
    }


def is_commtrack(project, request):
    if project:
        return project.commtrack_enabled
    try:
        return 'commtrack.org' in request.get_host()
    except Exception:
        # get_host might fail for bad requests, e.g. scheduled reports
        return False


def get_per_domain_context(project, request=None):
    custom_logo_url = None
    if (project and project.has_custom_logo
            and domain_has_privilege(project.name, privileges.CUSTOM_BRANDING)):
        custom_logo_url = reverse('logo', args=[project.name])

    report_an_issue = True
    if (hasattr(request, 'couch_user') and request.couch_user and project
            and not request.couch_user.has_permission(project.name, 'report_an_issue')):
        report_an_issue = False
    return {
        'CUSTOM_LOGO_URL': custom_logo_url,
        'allow_report_an_issue': report_an_issue,
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


def js_api_keys(request):
    if hasattr(request, 'couch_user') and request.couch_user and not request.couch_user.analytics_enabled:
        return {}  # disable js analytics
    return {
        'ANALYTICS_IDS': settings.ANALYTICS_IDS,
        'ANALYTICS_CONFIG': settings.ANALYTICS_CONFIG,
        'MAPBOX_ACCESS_TOKEN': settings.MAPBOX_ACCESS_TOKEN,
    }


def websockets_override(request):
    # for some reason our proxy setup doesn't properly detect these things, so manually override them
    try:
        context = default(request)
        context['WEBSOCKET_URI'] = context['WEBSOCKET_URI'].replace(request.get_host(), settings.BASE_ADDRESS)
        if settings.DEFAULT_PROTOCOL == 'https':
            context['WEBSOCKET_URI'] = context['WEBSOCKET_URI'].replace('ws://', 'wss://')
        return context
    except Exception:
        # it's very unlikely this was needed, and some workflows (like scheduled reports) aren't
        # able to generate this, so don't worry about it.
        return {}


def enterprise_mode(request):
    return {
        'enterprise_mode': settings.ENTERPRISE_MODE,
        'is_saas_environment': settings.IS_SAAS_ENVIRONMENT,
        'restrict_domain_creation': settings.RESTRICT_DOMAIN_CREATION,
    }


def commcare_hq_names(request):
    return {
        'commcare_hq_names': {
            'COMMCARE_NAME': settings.COMMCARE_NAME,
            'COMMCARE_HQ_NAME': settings.COMMCARE_HQ_NAME
        }
    }
