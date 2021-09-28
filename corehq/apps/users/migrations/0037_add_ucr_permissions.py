from django.db import migrations

from corehq.apps.users.models import CouchUser
from corehq.toggles import USER_CONFIGURABLE_REPORTS, Toggle
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def add_ucr_permissions(apps, schema_editor):
    usernames = _get_usernames_for_toggle(USER_CONFIGURABLE_REPORTS)
    all_user_roles = []
    user_objs = [CouchUser.get_by_username(username) for username in usernames]

    for user_obj in user_objs:
        # For the cases when an invalid username is present in toggle
        if user_obj:
            all_user_roles += [
                user_obj.get_role(domain)
                for domain in user_obj.domains
            ]
    user_roles = [role for role in all_user_roles if role and role.name != 'Admin']
    for role in user_roles:
        permissions = role.permissions
        if permissions.edit_ucrs:
            permissions.edit_ucrs = True
            role.set_permissions(permissions.to_list())


def _get_usernames_for_toggle(toggle):
    toggle_obj = Toggle.get(toggle.slug)
    return [user for user in toggle_obj.enabled_users
            if not user.startswith("domain:")]


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0036_reset_user_history_records'),
    ]

    operations = [
        migrations.RunPython(add_ucr_permissions, migrations.RunPython.noop)
    ]
