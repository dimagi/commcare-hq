from corehq.apps.users.models import UserRole, HqPermissions


class UserRolePresets:
    # These names are stored in the DB and used as identifiers, I'd avoid renaming
    APP_EDITOR = "App Editor"
    READ_ONLY = "Read Only"
    FIELD_IMPLEMENTER = "Field Implementer"
    BILLING_ADMIN = "Billing Admin"
    MOBILE_WORKER = "Mobile Worker Default"

    INITIAL_ROLES = {
        READ_ONLY: lambda: HqPermissions(view_reports=True),
        APP_EDITOR: lambda: HqPermissions(edit_apps=True, view_apps=True, view_reports=True),
        FIELD_IMPLEMENTER: lambda: HqPermissions(edit_commcare_users=True,
                                                 view_commcare_users=True,
                                                 edit_groups=True,
                                                 view_groups=True,
                                                 edit_locations=True,
                                                 view_locations=True,
                                                 edit_shared_exports=True,
                                                 view_reports=True),
        BILLING_ADMIN: lambda: HqPermissions(edit_billing=True),
        MOBILE_WORKER: lambda: HqPermissions(access_mobile_endpoints=True,
                                             report_an_issue=True,
                                             access_all_locations=True,
                                             access_api=False,
                                             download_reports=False)
    }


def get_custom_roles_for_domain(domain):
    """Returns a list of roles for the domain excluding archived roles
    and 'default' roles."""
    return [
        role for role in UserRole.objects.get_by_domain(domain)
        if role.name not in UserRolePresets.INITIAL_ROLES
    ]


def archive_custom_roles_for_domain(domain):
    custom_roles = get_custom_roles_for_domain(domain)
    for role in custom_roles:
        role.is_archived = True
        role.save()


def unarchive_roles_for_domain(domain):
    archived_roles = UserRole.objects.filter(domain=domain, is_archived=True)
    for role in archived_roles:
        role.is_archived = False
        role.save()


def reset_initial_roles_for_domain(domain):
    for role in UserRole.objects.get_by_domain(domain):
        if role.name in UserRolePresets.INITIAL_ROLES:
            preset_permissions = UserRolePresets.INITIAL_ROLES.get(role.name)()
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
