from corehq.apps.users.models import UserRole, HqPermissions
from corehq.apps.users.permissions import COMMCARE_ANALYTICS_USER_ROLES


class UserRolePresets:
    # These names are stored in the DB and used as identifiers, I'd avoid renaming
    APP_EDITOR = "App Editor"
    READ_ONLY = "Read Only"
    FIELD_IMPLEMENTER = "Field Implementer"
    BILLING_ADMIN = "Billing Admin"
    MOBILE_WORKER = "Mobile Worker Default"
    ATTENDANCE_COORDINATOR = "Attendance Coordinator"

    INITIAL_ROLES = {
        READ_ONLY: lambda: HqPermissions(view_reports=True, download_reports=True),
        APP_EDITOR: lambda: HqPermissions(edit_apps=True,
                                          view_apps=True,
                                          view_reports=True,
                                          download_reports=True),
        FIELD_IMPLEMENTER: lambda: HqPermissions(edit_commcare_users=True,
                                                 view_commcare_users=True,
                                                 edit_groups=True,
                                                 view_groups=True,
                                                 edit_locations=True,
                                                 view_locations=True,
                                                 edit_shared_exports=True,
                                                 view_reports=True,
                                                 download_reports=True),
        BILLING_ADMIN: lambda: HqPermissions(edit_billing=True),
        MOBILE_WORKER: lambda: HqPermissions(access_mobile_endpoints=True,
                                             access_web_apps=True,
                                             report_an_issue=True,
                                             access_all_locations=True),
    }

    PRIVILEGED_ROLES = {
        # ATTENDANCE_COORDINATOR is not a custom role. It is only
        # available to domains on higher subscription plans.
        ATTENDANCE_COORDINATOR: lambda: HqPermissions(
            manage_attendance_tracking=True,
            edit_groups=True,
            view_groups=True,
            edit_users_in_groups=True,
            edit_data=True,
            edit_apps=True,
            view_apps=True,
            access_web_apps=True,
            edit_reports=True,
            download_reports=True,
            view_reports=True
        )
    }


def _get_default_roles():
    """
    Although not all domain will have the privileged roles, it should not be considered as a custom role
    """
    return {**UserRolePresets.INITIAL_ROLES, **UserRolePresets.PRIVILEGED_ROLES}


def get_custom_roles_for_domain(domain):
    """Returns a list of roles for the domain excluding archived roles
    and 'default' roles."""
    return [
        role for role in UserRole.objects.get_by_domain(domain)
        if role.name not in _get_default_roles()
    ]


def archive_custom_roles_for_domain(domain):
    custom_roles = get_custom_roles_for_domain(domain)
    for role in custom_roles:
        role.is_archived = True
        role.save()


def archive_attendance_coordinator_role_for_domain(domain):
    """Archive the Attendance Coordinator for `domain`"""
    role = UserRole.objects.filter(name=UserRolePresets.ATTENDANCE_COORDINATOR, domain=domain).first()
    if not role:
        return
    role.is_archived = True
    role.save()


def unarchive_roles_for_domain(domain):
    """Unarchive all custome roles for `domain`"""
    privileged_role_names = list(UserRolePresets.PRIVILEGED_ROLES.keys())
    archived_roles = UserRole.objects.filter(domain=domain, is_archived=True
                                             ).exclude(name__in=privileged_role_names)
    for role in archived_roles:
        role.is_archived = False
        role.save()


def reset_initial_roles_for_domain(domain):
    default_roles = _get_default_roles()
    for role in UserRole.objects.get_by_domain(domain):
        if role.name in default_roles:
            preset_permissions = default_roles.get(role.name)()
            role.set_permissions(preset_permissions.to_list())


def initialize_domain_with_default_roles(domain):
    """Outside of tests this is only called when creating a new domain"""
    for role_name, permissions_fn in UserRolePresets.INITIAL_ROLES.items():
        UserRole.create(
            domain,
            role_name,
            permissions=permissions_fn(),
            is_commcare_user_default=role_name is UserRolePresets.MOBILE_WORKER,
        )


def enable_attendance_coordinator_role_for_domain(domain):
    role = UserRole.objects.filter(name=UserRolePresets.ATTENDANCE_COORDINATOR, domain=domain).first()
    if not role:
        role_name = UserRolePresets.ATTENDANCE_COORDINATOR
        UserRole.create(
            domain,
            role_name,
            permissions=UserRolePresets.PRIVILEGED_ROLES[role_name]()
        )
        return

    if role.is_archived:
        role.is_archived = False
        role.save()


def get_commcare_analytics_access_for_user_domain(couch_user, domain):
    domain_membership = couch_user.get_domain_membership(domain)
    is_admin = domain_membership.is_admin

    if is_admin:
        permissions = {
            "can_edit": True,
            "can_view": True,
        }
        cca_roles = COMMCARE_ANALYTICS_USER_ROLES
    else:
        domain_role_permissions = domain_membership.role.permissions
        permissions = {
            "can_edit": domain_role_permissions.edit_commcare_analytics,
            "can_view": domain_role_permissions.view_commcare_analytics,
        }
        if domain_role_permissions.commcare_analytics_roles:
            cca_roles = COMMCARE_ANALYTICS_USER_ROLES
        else:
            cca_roles = domain_role_permissions.commcare_analytics_roles_list

    return {
        "permissions": permissions,
        "roles": cca_roles,
    }
