import logging
from django.core.urlresolvers import reverse
from corehq import privileges, toggles
from django_prbac.models import Role
import toggle

logger = logging.getLogger(__name__)

LOGO_PRIVILEGES = [
    privileges.LOGO_ENTERPRISE,
    privileges.LOGO_ADVANCED,
    privileges.LOGO_PRO,
    privileges.LOGO_STANDARD,
    privileges.LOGO_COMMUNITY,
]

COMMCARE = {
    privileges.LOGO_COMMUNITY: 'hqstyle/img/plan-logos/commcare/community.png',
    privileges.LOGO_STANDARD: 'hqstyle/img/plan-logos/commcare/standard.png',
    privileges.LOGO_PRO: 'hqstyle/img/plan-logos/commcare/pro.png',
    privileges.LOGO_ADVANCED: 'hqstyle/img/plan-logos/commcare/advanced.png',
    privileges.LOGO_ENTERPRISE: 'hqstyle/img/plan-logos/commcare/enterprise.png',
}

COMMCARE_DEFAULT = 'hqstyle/img/commcare-logo.png'

COMMTRACK = {
    privileges.LOGO_COMMUNITY: 'hqstyle/img/plan-logos/commtrack/community.png',
    privileges.LOGO_STANDARD: 'hqstyle/img/plan-logos/commtrack/standard.png',
    privileges.LOGO_PRO: 'hqstyle/img/plan-logos/commtrack/pro.png',
    privileges.LOGO_ADVANCED: 'hqstyle/img/plan-logos/commtrack/advanced.png',
    privileges.LOGO_ENTERPRISE: 'hqstyle/img/plan-logos/commtrack/enterprise.png',
}

COMMTRACK_DEFAULT = 'hqstyle/img/commtrack-logo.png'

COMMCONNECT = {
    privileges.LOGO_COMMUNITY: 'hqstyle/img/plan-logos/commconnect/community.png',
    privileges.LOGO_STANDARD: 'hqstyle/img/plan-logos/commconnect/standard.png',
    privileges.LOGO_PRO: 'hqstyle/img/plan-logos/commconnect/pro.png',
    privileges.LOGO_ADVANCED: 'hqstyle/img/plan-logos/commconnect/advanced.png',
    privileges.LOGO_ENTERPRISE: 'hqstyle/img/plan-logos/commconnect/enterprise.png',
}

COMMCONNECT_DEFAULT = 'hqstyle/img/commconnect-logo.png'


def get_logo(project, request):
    if not project:
        return get_logo_by_host(request)

    if project.has_custom_logo:
        return reverse('logo', args=[project.name])

    if project.has_commtrack_enabled:
        return


def get_logo_by_privilege(request, product_logos, default_logo=None):
    """
    Matches logo to plan / privilege type.
    """
    if not request:
        return default_logo

    # skip for non-demo users for now:
    if (not request or hasattr(request, 'user')
        or not toggle.shortcuts.toggle_enabled(toggles.PRBAC_DEMO, request.user.username)):
        return default_logo

    if not hasattr(request, 'role'):
        logger.debug('require_privilege invoked with no role on request object')

    available_privileges = Role.objects.filter(slug__in=LOGO_PRIVILEGES)
    for priv in available_privileges:
        if request.role.has_privilege(priv):
            return product_logos.get(priv.slug)

    return default_logo


def get_logo_by_host(request):
    """
    Attempts to match logo to host url.
    """
    try:
        if 'commtrack.org' in request.get_host():
            return COMMTRACK_DEFAULT
    except Exception:
        # get_host might fail for bad requests, e.g. scheduled reports
        pass
    return COMMCARE_DEFAULT
