from django.http import HttpResponseForbidden
from corehq.apps.domain.decorators import login_and_domain_required

def require_permission(permission):
    def decorator(view_func):
        def _inner(request, domain, *args, **kwargs):
            if hasattr(request, "couch_user") and (request.user.is_superuser or request.couch_user.has_permission(domain, permission)):
                return login_and_domain_required(view_func)(request, domain, *args, **kwargs)
            else:
                return HttpResponseForbidden()
        return _inner
    return decorator