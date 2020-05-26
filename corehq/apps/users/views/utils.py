from django.utils.translation import ugettext as _

from corehq.apps.users.models import (
    AdminUserRole,
    UserRole,
)


def get_editable_role_choices(domain, couch_user, allow_admin_role):
    """
    :param domain: roles for domain
    :param couch_user: user accessing the roles
    :param allow_admin_role: to include admin role, in case user is admin
    """
    def role_to_choice(role):
        return (role.get_qualified_id(),
                role.name or _('(No Name)'))

    roles = UserRole.by_domain(domain)
    if not couch_user.is_domain_admin(domain):
        roles = [role for role in roles if role.is_non_admin_editable]
    elif allow_admin_role:
        roles = [AdminUserRole(domain=domain)] + roles
    return [role_to_choice(role) for role in roles]
