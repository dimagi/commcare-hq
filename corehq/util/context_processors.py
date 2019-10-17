import datetime

from django.conf import settings
from django.http import Http404
from django.urls import resolve, reverse
from django_prbac.utils import has_privilege
from ws4redis.context_processors import default

from corehq import privileges, toggles
from corehq.apps.analytics import ab_tests
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.accounting.utils import domain_has_privilege
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
    from corehq import toggles
    custom_logo_url = None
    if (project and project.has_custom_logo and
            domain_has_privilege(project.name, privileges.CUSTOM_BRANDING)):
        custom_logo_url = reverse('logo', args=[project.name])

    def allow_report_issue(user, domain):
        if toggles.ICDS.enabled(domain) and user.is_commcare_user():
            role = user.get_domain_membership(domain).role
            if not role:
                return False
        return user.has_permission(domain, 'report_an_issue')

    if getattr(request, 'couch_user', None) and project:
        allow_report_an_issue = allow_report_issue(request.couch_user, project.name)
    elif settings.ENTERPRISE_MODE:
        if not getattr(request, 'couch_user', None):
            allow_report_an_issue = False
        elif request.couch_user.is_web_user():
            allow_report_an_issue = True
        else:
            allow_report_an_issue = allow_report_issue(request.couch_user, request.couch_user.domain)
    else:
        allow_report_an_issue = True

    return {
        'CUSTOM_LOGO_URL': custom_logo_url,
        'allow_report_an_issue': allow_report_an_issue,
        'EULA_COMPLIANCE': getattr(settings, 'EULA_COMPLIANCE', False),
    }


def domain(request):
    """Global per-domain context variables"""
    project = getattr(request, 'project', None)
    return get_per_domain_context(project, request=request)


def domain_billing_context(request):
    is_domain_billing_admin = False
    restrict_domain_creation = settings.RESTRICT_DOMAIN_CREATION
    if getattr(request, 'couch_user', None) and getattr(request, 'domain', None):
        account = BillingAccount.get_account_by_domain(request.domain)
        if account:
            if has_privilege(request, privileges.ACCOUNTING_ADMIN):
                is_domain_billing_admin = True
            elif account.has_enterprise_admin(request.couch_user.username):
                is_domain_billing_admin = True
            if not is_domain_billing_admin:
                restrict_domain_creation = restrict_domain_creation or account.restrict_domain_creation
    return {
        'IS_DOMAIN_BILLING_ADMIN': is_domain_billing_admin,
        'restrict_domain_creation': restrict_domain_creation,
    }


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


def js_toggles(request):
    if not getattr(request, 'couch_user', None):
        return {}
    if not getattr(request, 'project', None):
        return {}
    from corehq import toggles, feature_previews
    domain = request.project.name
    return {
        'toggles_dict': toggles.toggle_values_by_name(username=request.couch_user.username, domain=domain),
        'previews_dict': feature_previews.preview_values_by_name(domain=domain)
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
    }


def commcare_hq_names(request=None):
    return {
        'commcare_hq_names': {
            'COMMCARE_NAME': _get_cc_name(request, 'COMMCARE_NAME'),
            'COMMCARE_HQ_NAME': _get_cc_name(request, 'COMMCARE_HQ_NAME'),
        },
    }


def emails(request=None):
    """
    Emails commonly referenced in user-facing templates.
    Please use (and add to) these references rather than hard-coding or adding
    a page-specific context variable.
    """
    return {
        'SALES_EMAIL': settings.SALES_EMAIL,
        'SUPPORT_EMAIL': settings.SUPPORT_EMAIL,
        'PRIVACY_EMAIL': settings.PRIVACY_EMAIL,
        'INVOICING_CONTACT_EMAIL': settings.INVOICING_CONTACT_EMAIL,
    }


def _get_cc_name(request, var):
    value = getattr(settings, var)
    if isinstance(value, str):
        return value

    if request is None:
        # There are a few places where we do not have access to a request,
        # for these we return the default name for the enviroment.
        return value['default']

    try:
        host = request.get_host()
    except KeyError:
        # In reporting code we create an HttpRequest object inside python which
        # does not have an HTTP_HOST attribute. Its unclear what host would be
        # expected in that scenario, so we're showing the default.
        # The true fix for this lies in removing fake requests from scheduled reports
        host = 'default'

    return value.get(host) or value['default']


def mobile_experience(request):
    show_mobile_ux_warning = False
    mobile_ux_cookie_name = ''
    if (hasattr(request, 'couch_user') and
            hasattr(request, 'user_agent') and
            settings.SERVER_ENVIRONMENT in ['production', 'staging', 'localdev']):
        mobile_ux_cookie_name = '{}-has-seen-mobile-ux-warning'.format(request.couch_user.get_id)
        show_mobile_ux_warning = (
            not request.COOKIES.get(mobile_ux_cookie_name) and
            request.user_agent.is_mobile and
            request.user.is_authenticated and
            request.user.is_active and
            not mobile_experience_hidden_by_toggle(request)
        )
    return {
        'show_mobile_ux_warning': show_mobile_ux_warning,
        'mobile_ux_cookie_name': mobile_ux_cookie_name,
    }


def mobile_experience_hidden_by_toggle(request):
    from corehq import toggles
    user = request.couch_user
    for project in user.domains:
        if toggles.HIDE_HQ_ON_MOBILE_EXPERIENCE.enabled(project, toggles.NAMESPACE_DOMAIN):
            return True
    return False


def banners(request):
    is_logged_in_user = hasattr(request, 'user') and request.user.is_authenticated
    has_subscription = hasattr(request, 'subscription')
    if not (settings.IS_SAAS_ENVIRONMENT and is_logged_in_user and has_subscription):
        return {}

    context = {}
    if request.subscription.is_trial:
        delta = request.subscription.date_end - datetime.date.today()
        context.update({
            'num_trial_days_remaining': max(0, delta.days),
            'show_trial_banner': True,
        })
    elif request.subscription.is_community:
        context.update({
            'show_community_banner': True,
        })
    return context


def get_demo(request):
    is_user_not_logged_in = getattr(request, 'user', None) and not request.user.is_authenticated
    is_hubspot_enabled = settings.ANALYTICS_IDS.get('HUBSPOT_API_ID')
    context = {}
    if settings.IS_SAAS_ENVIRONMENT and is_hubspot_enabled and is_user_not_logged_in:
        context.update({
            'is_demo_visible': True,
        })
    return context
