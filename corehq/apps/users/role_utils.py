from corehq.apps.users.models import UserRolePresets, Permissions, SQLUserRole


def get_read_only_role_for_domain(domain):
    try:
        return SQLUserRole.objects.get_by_domain_and_name(domain, UserRolePresets.READ_ONLY)[0]
    except IndexError:
        return get_or_create_role_with_permissions(
            domain,
            UserRolePresets.get_permissions(UserRolePresets.READ_ONLY),
            UserRolePresets.READ_ONLY
        )


def get_or_create_role_with_permissions(domain, permissions, name, **kwargs):
    if isinstance(permissions, dict):
        permissions = Permissions.wrap(permissions)
    roles = SQLUserRole.objects.by_domain(domain)
    # try to get a matching role from the db
    for role in roles:
        if role.permissions == permissions:
            return role
    # otherwise create it

    return SQLUserRole.create(domain, name, permissions, **kwargs)


def get_custom_roles_for_domain(domain):
    return [
        role for role in SQLUserRole.objects.by_domain(domain)
        if role.name not in UserRolePresets.INITIAL_ROLES
    ]


def reset_initial_roles_for_domain(domain):
    initial_roles = [
        role for role in SQLUserRole.objects.by_domain(domain)
        if role.name in UserRolePresets.INITIAL_ROLES
    ]
    for role in initial_roles:
        permissions = UserRolePresets.get_permissions(role.name)
        role.set_permissions(permissions.to_list())


def archive_custom_roles_for_domain(domain):
    custom_roles = get_custom_roles_for_domain(domain)
    for role in custom_roles:
        role.is_archived = True
    SQLUserRole.objects.bulk_update(custom_roles, fields=["is_archived"])


def unarchive_roles_for_domain(domain):
    SQLUserRole.objects.filter(domain=domain).update(is_archived=False)


def initialize_roles_for_domain(domain):
    for role_name in UserRolePresets.INITIAL_ROLES:
        get_or_create_role_with_permissions(
            domain, UserRolePresets.get_permissions(role_name), role_name
        )


def get_all_role_names_for_domain(domain_name):
    presets = set(UserRolePresets.NAME_ID_MAP.keys())
    custom = set([role.name for role in SQLUserRole.objects.by_domain(domain_name)])
    return presets | custom
