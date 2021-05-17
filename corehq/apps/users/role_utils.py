from corehq.apps.users.models import Permissions, UserRole


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
