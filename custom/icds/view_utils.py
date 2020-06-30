from functools import wraps

from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy, ugettext as _
from django.conf import settings
from django.http import HttpResponse

from corehq import toggles
from corehq.apps.hqwebapp.views import no_permissions
from custom.icds.const import ICDS_DOMAIN, IS_ICDS_ENVIRONMENT
from corehq.apps.users.models import DomainMembershipError

DATA_INTERFACE_ACCESS_DENIED = mark_safe(ugettext_lazy(
    "This project has blocked access to interfaces that edit data for forms and cases"
))


def check_data_interfaces_blocked_for_domain(view_func):
    @wraps(view_func)
    def _inner(request, domain, *args, **kwargs):
        if is_icds_cas_project(domain):
            return no_permissions(request, message=DATA_INTERFACE_ACCESS_DENIED)
        else:
            return view_func(request, domain, *args, **kwargs)
    return _inner


def is_icds_cas_project(domain):
    return IS_ICDS_ENVIRONMENT and domain == ICDS_DOMAIN


def check_app_access(domain, user, app):
    if (
        settings.SERVER_ENVIRONMENT == 'icds-staging'
        and toggles.ROLE_WEBAPPS_PERMISSIONS.enabled(domain)
    ):
        try:
            role = user.get_role(domain)
        except DomainMembershipError:
            return HttpResponse(_('User is not a member of this project'), status=404), None
        else:
            if not (role and role.permissions.view_web_app(app)):
                return HttpResponse(_('User is not allowed on this app'), status=406), None
    return None
