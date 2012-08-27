from django.http import HttpResponseForbidden
from corehq.apps.domain.decorators import login_and_domain_required

def require_permission(permission, data=None, login_decorator=login_and_domain_required):
    try:
        permission = permission.name
    except AttributeError:
        try:
            permission = permission.__name__
        except AttributeError:
            pass
    def decorator(view_func):
        def _inner(request, domain, *args, **kwargs):
            if hasattr(request, "couch_user") and (request.user.is_superuser or request.couch_user.has_permission(domain, permission, data=data)):
                if login_decorator:
                    return login_decorator(view_func)(request, domain, *args, **kwargs)
                else:
                    return view_func(request, domain, *args, **kwargs)
            else:
                return HttpResponseForbidden()
        return _inner
    return decorator
