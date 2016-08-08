from django.http import Http404, HttpResponse
from django.core.exceptions import PermissionDenied
from corehq.apps.domain.decorators import login_and_domain_required, domain_specific_login_redirect
from functools import wraps
from corehq.apps.users.models import CouchUser, CommCareUser
from django.utils.translation import ugettext as _
from dimagi.utils.web import json_response

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
                if request.is_ajax():
                    return HttpResponse(_("Sorry, you don't have permission to do this action!"), status=403)
                raise PermissionDenied()

        if login_decorator:
            return login_decorator(_inner)
        else:
            return _inner

    return decorator


def get_permission_name(permission):
    try:
        return permission.name
    except AttributeError:
        try:
            return permission.__name__
        except AttributeError:
            return None


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


def ensure_active_user():
    def decorator(fn):
        @wraps(fn)
        def _inner(request, *args, **kwargs):
            """
            ensures active user for sync and form receive requests
            returns the error code which should be present in app_string for translation and also shares
            the default response which can be used in case the translation is missing
            """
            valid = True
            couch_user = CouchUser.from_django_user(request.user)
            if couch_user:
                valid, message, error_code = ensure_active_user_by_username(couch_user.username)

            if not valid:
                # respond with apt error message and status code 406(unacceptable)
                return json_response({
                    "error": error_code,
                    "default_response": message
                }, status_code=406)
            else:
                return fn(request, *args, **kwargs)
        return _inner
    return decorator


def ensure_active_user_by_username(username):
    ccu = CommCareUser.get_by_username(username)
    valid, message, error_code = True, None, None
    if ccu and not ccu.is_active:
        valid, message, error_code = False, 'User deactivated', 'mobile.app.translation.user.is.deactivated'
    elif CommCareUser.get_deleted_by_username(username):
        valid, message, error_code = False, 'User deleted', 'mobile.app.translation.user.is.deleted'
    return valid, message, error_code
