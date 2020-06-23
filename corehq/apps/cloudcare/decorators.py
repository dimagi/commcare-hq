from functools import wraps

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions


def require_cloudcare_access_ex():
    """
    Decorator for cloudcare users. Should require either access web apps
    permissions or they should be a mobile user.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _inner(request, domain, *args, **kwargs):
            if hasattr(request, "couch_user"):
                if request.couch_user.is_web_user():
                    return require_permission(Permissions.access_web_apps)(view_func)(request, domain, *args, **kwargs)
                else:
                    assert request.couch_user.is_commcare_user(), \
                        "user was neither a web user or a commcare user!"
                    return login_and_domain_required(view_func)(request, domain, *args, **kwargs)
            return login_and_domain_required(view_func)(request, domain, *args, **kwargs)
        return _inner
    return decorator

require_cloudcare_access = require_cloudcare_access_ex()
