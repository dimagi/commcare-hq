from corehq.apps.users.models import Permissions, SQLUserRole, UserRolePresets


def get_or_create_role_with_permissions(domain, name, permissions):
    """This function will check all existing roles in the domain
    for a role with matching permissions before creating a new role.
    """
    if isinstance(permissions, dict):
        permissions = Permissions.wrap(permissions)

    roles = SQLUserRole.objects.get_by_domain(domain)

    # try to get a matching role from the db
    for role in roles:
        if role.permissions == permissions:
            return role

    # otherwise create it
    return SQLUserRole.create(domain, name, permissions=permissions)


def get_custom_roles_for_domain(domain):
    return [
        role for role in SQLUserRole.objects.get_by_domain(domain)
        if role.name not in UserRolePresets.INITIAL_ROLES
    ]


def archive_custom_roles_for_domain(domain):
    custom_roles = get_custom_roles_for_domain(domain)
    for role in custom_roles:
        role.is_archived = True
        role.save()


def unarchive_roles_for_domain(domain):
    all_roles = SQLUserRole.objects.filter(domain=domain, is_archived=True)
    for role in all_roles:
        role.is_archived = False
        role.save()


def reset_initial_roles_for_domain(domain):
    initial_roles = [
        role for role in SQLUserRole.objects.get_by_domain(domain)
        if role.name in UserRolePresets.INITIAL_ROLES
    ]
    for role in initial_roles:
        role.set_permissions(UserRolePresets.get_permissions(role.name).to_list())
        role._migration_do_sync()  # sync role to couch


def initialize_domain_with_default_roles(domain):
    for role_name in UserRolePresets.INITIAL_ROLES:
        get_or_create_role_with_permissions(
            domain, role_name, UserRolePresets.get_permissions(role_name)
        )
