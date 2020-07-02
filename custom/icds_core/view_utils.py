from functools import wraps

from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy

from corehq import toggles
from corehq.apps.hqwebapp.views import no_permissions
from custom.icds.const import ICDS_DOMAIN, IS_ICDS_ENVIRONMENT

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


def icds_pre_release_features(user):
    return toggles.ICDS_DASHBOARD_REPORT_FEATURES.enabled(user.username)
