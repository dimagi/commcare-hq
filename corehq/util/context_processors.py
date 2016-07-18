from django.conf import settings
from django.core.urlresolvers import resolve, reverse
from django.http import Http404
from ws4redis.context_processors import default
from corehq.apps.accounting.utils import domain_has_privilege
from corehq import privileges

COMMCARE = 'commcare'
COMMTRACK = 'commtrack'


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


def get_per_domain_context(project, request=None):
    custom_logo_url = None
    if (project and project.has_custom_logo
        and domain_has_privilege(project.name, privileges.CUSTOM_BRANDING)
    ):
        custom_logo_url = reverse('logo', args=[project.name])

    return {
        'CUSTOM_LOGO_URL': custom_logo_url,
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
    d = {}
    d.update(settings.ANALYTICS_IDS)
    d.update({"ANALYTICS_CONFIG": settings.ANALYTICS_CONFIG})
    d['MAPBOX_ACCESS_TOKEN'] = settings.MAPBOX_ACCESS_TOKEN
    return d


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
