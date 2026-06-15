from django.http import JsonResponse
from django.views.decorators.http import require_GET

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.registry.utils import get_data_registry_dropdown_options
from corehq.apps.reports.models import TableauVisualization
from corehq.apps.reports.util import get_possible_reports
from corehq.apps.users.models import PARAMETERIZED_PERMISSIONS, HqPermissions
from corehq.apps.users.views import _commcare_analytics_roles_options
from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE
from corehq.util.quickcache import quickcache


@require_GET
@login_and_domain_required
def my_role(request, domain):
    """Return the requesting user's role label, admin flags, and permission booleans."""
    return JsonResponse(_build_my_role(request.couch_user, domain))


@quickcache(['couch_user.user_id', 'domain'], timeout=30 * 60)
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
            list_field = PARAMETERIZED_PERMISSIONS[name]
            raw_items = list(getattr(role_permissions, list_field))
            if granted:
                permissions[name] = True
            elif raw_items:
                permissions[name] = {
                    'scope': 'limited',
                    'items': _resolve_item_names(domain, list_field, raw_items),
                }
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


def _resolve_item_names(domain, list_field, raw_items):
    """Map raw IDs to user-facing names; unknown IDs fall through unchanged."""
    name_map = _name_map_for(domain, list_field)
    return [name_map.get(item, item) for item in raw_items]


def _name_map_for(domain, list_field):
    """Build the {raw_id: friendly_name} map for one parameterized list."""
    if list_field == 'view_report_list':
        return {r['path']: r['name'] for r in get_possible_reports(domain)}

    if list_field == 'view_tableau_list':
        return {
            str(viz.id): viz.name
            for viz in TableauVisualization.objects.filter(domain=domain)
        }

    if list_field == 'web_apps_list':
        return {app._id: app.name for app in get_cloudcare_apps(domain)}

    if list_field in ('manage_data_registry_list', 'view_data_registry_contents_list'):
        return {r['slug']: r['name'] for r in get_data_registry_dropdown_options(domain)}

    if list_field == 'commcare_analytics_roles_list':
        return {r['slug']: r['name'] for r in _commcare_analytics_roles_options()}

    if list_field == 'edit_user_profile_list':
        definition = CustomDataFieldsDefinition.get(domain, CUSTOM_USER_DATA_FIELD_TYPE)
        if definition is None:
            return {}
        return {str(profile.id): profile.name for profile in definition.get_profiles()}

    return {}
