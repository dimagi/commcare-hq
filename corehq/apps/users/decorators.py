from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.utils.translation import gettext as _

from corehq import toggles
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    redirect_for_login_or_domain,
)
from corehq.apps.users.dbaccessors import get_deleted_user_by_username
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.util.view_utils import is_ajax


def require_permission_raw(permission_check,
                           login_decorator=login_and_domain_required,
                           view_only_permission_check=None,
                           permission_check_v2=None):
    """
    A way to do more fine-grained permissions via decorator. The permission_check should be
    a function that takes in a couch_user and a domain and returns True if that user can access
    the page, otherwise false.

    If `permission_check_v2` is specified it will be used instead of permission_check.
    This is to allow for changing the permission-checking API without having to update every
    call at the same time.

    permission_check_v2 takes in a *request* instead of a *user* so it can do more explicit
    checking (e.g. check the exact API key that was used).
    """
    def decorator(view_func):
        @wraps(view_func)
        def _inner(request, domain, *args, **kwargs):
            if not hasattr(request, "couch_user"):
                return redirect_for_login_or_domain(request)
            elif permission_check_v2 is not None:
                if permission_check_v2(request, domain):
                    return view_func(request, domain, *args, **kwargs)
                else:
                    raise PermissionDenied()
            elif request.user.is_superuser or permission_check(request.couch_user, domain):
                request.is_view_only = False
                return view_func(request, domain, *args, **kwargs)
            elif (view_only_permission_check is not None
                  and view_only_permission_check(request.couch_user, domain)):
                request.is_view_only = True
                return view_func(request, domain, *args, **kwargs)
            else:
                if is_ajax(request):
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


def require_api_permission(permission, data=None, login_decorator=login_and_domain_required):
    permission = get_permission_name(permission) or permission
    # ensure all requests also have this permission
    api_access_permission = 'access_api'
    permissions_to_check = {permission, api_access_permission}

    def permission_check(request, domain):
        # first check user permissions and return immediately if not valid
        user_has_permission = all(
            request.couch_user.has_permission(domain, p, data=data)
            for p in permissions_to_check
        )
        if not user_has_permission:
            return False

        # then check domain and role scopes, if present
        api_key = getattr(request, 'api_key', None)

        if not api_key:
            return True  # only api keys support additional checks
        elif api_key.role:
            return (
                api_key.role.domain == domain
                and all(api_key.role.permissions.has(p, data) for p in permissions_to_check)
            )
        elif api_key.domain:
            # we've already checked for user and role permissions so all that's left is domain matching
            return domain == api_key.domain
        else:
            # unscoped API key defaults to user permissions
            return True

    return require_permission_raw(
        None, login_decorator,
        view_only_permission_check=None,
        permission_check_v2=permission_check,
    )


def require_permission(permission,
                       data=None,
                       login_decorator=login_and_domain_required,
                       view_only_permission=None):
    permission = get_permission_name(permission) or permission
    permission_check = lambda couch_user, domain: couch_user.has_permission(domain, permission, data=data)

    view_only_check = None
    if view_only_permission is not None:
        view_only_permission = (get_permission_name(view_only_permission)
                                or view_only_permission)

        def _check_permission(_user, _domain):
            return _user.has_permission(_domain, view_only_permission, data=data)

        view_only_check = _check_permission

    return require_permission_raw(
        permission_check, login_decorator,
        view_only_permission_check=view_only_check
    )


require_can_edit_web_users = require_permission('edit_web_users')
require_can_edit_or_view_web_users = require_permission(
    'edit_web_users', view_only_permission='view_web_users'
)
require_can_edit_commcare_users = require_permission('edit_commcare_users')
require_can_edit_or_view_commcare_users = require_permission(
    'edit_commcare_users', view_only_permission='view_commcare_users'
)
require_can_edit_groups = require_permission('edit_groups')
require_can_edit_or_view_groups = require_permission(
    'edit_groups', view_only_permission='view_groups'
)
require_can_view_roles = require_permission('view_roles')
require_can_login_as = require_permission_raw(lambda user, domain: user.can_login_as(domain))
require_can_coordinate_events = require_permission('manage_attendance_tracking')
require_can_manage_domain_alerts = require_permission('manage_domain_alerts')


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
            return redirect_for_login_or_domain(request)
    return _inner


def require_can_use_filtered_user_download(view_func):
    @wraps(view_func)
    def _inner(request, domain, *args, **kwargs):
        if can_use_filtered_user_download(request.domain):
            return view_func(request, domain, *args, **kwargs)
        raise Http404()
    return _inner


def can_use_filtered_user_download(domain):
    if domain_has_privilege(domain, privileges.FILTERED_BULK_USER_DOWNLOAD):
        return True
    if toggles.DOMAIN_PERMISSIONS_MIRROR.enabled(domain):
        return True
    return False


def ensure_active_user_by_username(username):
    """
    :param username: ex: jordan@testapp-9.commcarehq.org
    :return
        valid: is True by default but is set to False for inactive/deleted user
        error_code: mapping in app_string for the user
        default_response: english description of the error to be used in case error_code missing
    """
    ccu = CommCareUser.get_by_username(username)
    valid, message, error_code = True, None, None
    if ccu and not ccu.is_active:
        valid, message, error_code = False, 'Your account has been deactivated, please contact your domain admin '\
                                            'to reactivate', 'user.deactivated'
    elif get_deleted_user_by_username(CommCareUser, username):
        valid, message, error_code = False, 'Your account has been deleted, please contact your domain admin to '\
                                            'request for restore', 'user.deleted'
    return valid, message, error_code
