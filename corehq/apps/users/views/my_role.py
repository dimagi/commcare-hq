from django.http import JsonResponse
from django.views.decorators.http import require_GET

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.users.models import PARAMETERIZED_PERMISSIONS, HqPermissions


@require_GET
@login_and_domain_required
def my_role(request, domain):
    """Return the requesting user's role label, admin flags, and permission booleans."""
    return JsonResponse(_build_my_role(request.couch_user, domain))


def _build_my_role(couch_user, domain):
    if couch_user.is_global_admin():
        return {'is_dimagi_admin': True}

    dm = couch_user.get_domain_membership(domain, allow_enterprise=True)
    account = BillingAccount.get_account_by_domain(domain)
    role_permissions = dm.role.permissions if dm.role else HqPermissions()

    permissions = {}
    for name in HqPermissions.permission_names():
        granted = couch_user.has_permission(domain, name)
        if name in PARAMETERIZED_PERMISSIONS:
            items = list(getattr(role_permissions, PARAMETERIZED_PERMISSIONS[name]))
            if granted:
                permissions[name] = True
            elif items:
                permissions[name] = {'scope': 'limited', 'items': items}
            else:
                permissions[name] = False
        else:
            permissions[name] = granted

    return {
        'role': couch_user.role_label(domain),
        'is_domain_admin': bool(dm.is_admin),
        'is_enterprise_admin': bool(
            account and account.has_enterprise_admin(couch_user.username)
        ),
        'permissions': permissions,
    }
