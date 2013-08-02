from django.core.urlresolvers import reverse
from django.http import HttpResponseForbidden
from corehq.apps.domain.decorators import login_and_domain_required, _redirect_for_login_or_domain
from corehq.apps.domain.models import Domain


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
            if not hasattr(request, "couch_user"):
                project = Domain.get_by_name(domain)
                login_url = reverse('login', kwargs={'domain_type': project.domain_type})
                return _redirect_for_login_or_domain(request, 'next', login_url)
            elif request.user.is_superuser or request.couch_user.has_permission(domain, permission, data=data):
                return view_func(request, domain, *args, **kwargs)
            else:
                return HttpResponseForbidden()

        if login_decorator:
            return login_decorator(_inner)
        else:
            return _inner

    return decorator
