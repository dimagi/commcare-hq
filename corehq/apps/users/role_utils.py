from corehq.apps.users.models import UserRole, UserRolePresets, Permissions
from corehq.apps.users.models_sql import SQLUserRole


def get_read_only_role_for_domain(domain):
    try:
        return UserRole.by_domain_and_name(domain, UserRolePresets.READ_ONLY)[0]
    except (IndexError, TypeError):
        return get_or_create_role_with_permissions(
            domain, UserRolePresets.get_permissions(
                UserRolePresets.READ_ONLY), UserRolePresets.READ_ONLY)


def get_or_create_role_with_permissions(domain, permissions, name):
    if isinstance(permissions, dict):
        permissions = Permissions.wrap(permissions)
    roles = UserRole.by_domain(domain)
    # try to get a matching role from the db
    for role in roles:
        if role.permissions == permissions:
            return role
    # otherwise create it

    role = UserRole(domain=domain, permissions=permissions, name=name)
    role.save()
    return role


def get_custom_roles_for_domain(domain):
    return [x for x in UserRole.by_domain(domain) if x.name not in UserRolePresets.INITIAL_ROLES]


def reset_initial_roles_for_domain(domain):
    initial_roles = [x for x in UserRole.by_domain(domain) if x.name in UserRolePresets.INITIAL_ROLES]
    for role in initial_roles:
        role.permissions = UserRolePresets.get_permissions(role.name)
        role.save()


def archive_custom_roles_for_domain(domain):
    custom_roles = get_custom_roles_for_domain(domain)
    for role in custom_roles:
        role.is_archived = True
        role.save()


def unarchive_roles_for_domain(domain):
    all_roles = UserRole.by_domain(domain, include_archived=True)
    for role in all_roles:
        if role.is_archived:
            role.is_archived = False
            role.save()


def initialize_roles_for_domain(domain):
    for role_name in UserRolePresets.INITIAL_ROLES:
        UserRole.get_or_create_with_permissions(
            domain, UserRolePresets.get_permissions(role_name), role_name)


def get_all_role_names_for_domain(domain_name):
    presets = set(UserRolePresets.NAME_ID_MAP.keys())
    custom = set([role.name for role in UserRole.by_domain(domain_name)])
    return presets | custom
