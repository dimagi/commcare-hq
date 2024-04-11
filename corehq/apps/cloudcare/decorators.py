from functools import wraps

from django.shortcuts import render
from no_exceptions.exceptions import Http403

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.utils.bootstrap import set_bootstrap_version5
from corehq import toggles
from corehq.apps.app_manager.dbaccessors import (
    get_apps_in_domain
)


def require_cloudcare_access_ex():
    """
    Decorator for cloudcare users. Should require either access web apps
    permissions or they should be a mobile user.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _inner(request, domain, *args, **kwargs):
            if toggles.DISABLE_WEB_APPS.enabled_for_request(request):

                apps_in_domain = get_apps_in_domain(domain)
                if (len(apps_in_domain) == 1):
                    app_or_domain_name = apps_in_domain[0].name
                else:
                    app_or_domain_name = domain

                context = {
                    "app_or_domain_name": app_or_domain_name,
                    "is_superuser": hasattr(request, "couch_user") and request.couch_user.is_superuser
                }
                set_bootstrap_version5()
                return render(request, "cloudcare/web_apps_disabled.html", context)
            if hasattr(request, "couch_user"):
                if not request.couch_user.can_access_any_web_apps(domain):
                    raise Http403()
                return view_func(request, domain, *args, **kwargs)
            return login_and_domain_required(view_func)(request, domain, *args, **kwargs)
        return _inner
    return decorator


require_cloudcare_access = require_cloudcare_access_ex()
