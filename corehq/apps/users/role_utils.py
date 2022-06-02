from corehq.apps.users.models import UserRole, Permissions
from django.utils.translation import gettext_noop


class UserRolePresets:
    # this is kind of messy, but we're only marking for translation (and not using gettext_lazy)
    # because these are in JSON and cannot be serialized
    # todo: apply translation to these in the UI
    # note: these are also tricky to change because these are just some default names,
    # that end up being stored in the database. Think about the consequences of changing these before you do.
    APP_EDITOR = gettext_noop("App Editor")
    READ_ONLY = gettext_noop("Read Only")
    FIELD_IMPLEMENTER = gettext_noop("Field Implementer")
    BILLING_ADMIN = gettext_noop("Billing Admin")
    MOBILE_WORKER = gettext_noop("Mobile Worker")
    INITIAL_ROLES = {
        READ_ONLY: lambda: Permissions(view_reports=True),
        APP_EDITOR: lambda: Permissions(edit_apps=True, view_apps=True, view_reports=True),
        FIELD_IMPLEMENTER: lambda: Permissions(edit_commcare_users=True,
                                               view_commcare_users=True,
                                               edit_groups=True,
                                               view_groups=True,
                                               edit_locations=True,
                                               view_locations=True,
                                               edit_shared_exports=True,
                                               view_reports=True),
        BILLING_ADMIN: lambda: Permissions(edit_billing=True),
        MOBILE_WORKER: lambda: Permissions(access_mobile_endpoints=True,
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
        UserRole.create(domain, role_name, permissions=permissions_fn())
