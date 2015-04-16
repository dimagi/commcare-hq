from django.http import Http404
from django.core.exceptions import PermissionDenied
from corehq.apps.domain.decorators import login_and_domain_required, domain_specific_login_redirect
from functools import wraps
from corehq.apps.users.models import CouchUser
from django.utils.translation import ugettext as _


def require_permission_raw(permission_check, login_decorator=login_and_domain_required):
    """
    A way to do more fine-grained permissions via decorator. The permission_check should be
    a function that takes in a couch_user and a domain and returns True if that user can access
    the page, otherwise false.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _inner(request, domain, *args, **kwargs):
            if not hasattr(request, "couch_user"):
                return domain_specific_login_redirect(request, domain)
            elif request.user.is_superuser or permission_check(request.couch_user, domain):
                return view_func(request, domain, *args, **kwargs)
            else:
                raise PermissionDenied()

        if login_decorator:
            return login_decorator(_inner)
        else:
            return _inner

    return decorator


def require_permission(permission, data=None, login_decorator=login_and_domain_required):
    try:
        permission = permission.name
    except AttributeError:
        try:
            permission = permission.__name__
        except AttributeError:
            pass
    permission_check = lambda couch_user, domain: couch_user.has_permission(domain, permission, data=data)
    return require_permission_raw(permission_check, login_decorator)


require_can_edit_web_users = require_permission('edit_web_users')
require_can_edit_commcare_users = require_permission('edit_commcare_users')

def require_permission_to_edit_user(view_func):
    # TODO add in location hierarchy permissions check
    @wraps(view_func)
    def _inner(request, domain, couch_user_id, *args, **kwargs):
        go_ahead = False
        if hasattr(request, "couch_user"):
            user = request.couch_user
            if user.is_superuser or user.user_id == couch_user_id or (hasattr(user, "is_domain_admin") and user.is_domain_admin()):
                go_ahead = True
            else:
                couch_user = CouchUser.get_by_user_id(couch_user_id)
                if not couch_user:
                    raise Http404()
                if couch_user.is_commcare_user() and request.couch_user.can_edit_commcare_users():
                    go_ahead = True
                elif couch_user.is_web_user() and request.couch_user.can_edit_web_users():
                    go_ahead = True
        if go_ahead:
            return login_and_domain_required(view_func)(request, domain, couch_user_id, *args, **kwargs)
        else:
            return domain_specific_login_redirect(request, domain)
    return _inner
