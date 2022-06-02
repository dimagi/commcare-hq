from corehq.apps.users.models import UserRole, UserRolePresets


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
        UserRole.create(domain, role_name, permissions=permissions_fn())
