from corehq.apps.users.models import Permissions, UserRole, UserRolePresets


def get_or_create_role_with_permissions(domain, name, permissions):
    """This function will check all existing roles in the domain
    for a role with matching permissions before creating a new role.
    """
    if isinstance(permissions, dict):
        permissions = Permissions.wrap(permissions)

    roles = UserRole.by_domain(domain)

    # try to get a matching role from the db
    for role in roles:
        if role.permissions == permissions:
            return role

    # otherwise create it
    role = UserRole.create(domain, name, permissions=permissions)
    role.save()
    return role


def get_read_only_role_for_domain(domain):
    """Get role with name "Read Only" or else create it
    with default permissions.

    Note: This does not check if the permissions of the returned role match the presets.
    """
    try:
        return UserRole.by_domain_and_name(domain, UserRolePresets.READ_ONLY)[0]
    except (IndexError, TypeError):
        return get_or_create_role_with_permissions(
            domain, UserRolePresets.READ_ONLY, UserRolePresets.get_permissions(UserRolePresets.READ_ONLY)
        )


def get_custom_roles_for_domain(domain):
    return [x for x in UserRole.by_domain(domain) if x.name not in UserRolePresets.INITIAL_ROLES]
