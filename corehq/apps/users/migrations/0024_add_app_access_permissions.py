from django.db import migrations

from dimagi.utils.couch.database import iter_docs

from corehq.apps.users.models import UserRole
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _migrate_web_apps_permissions_to_app_permissions(apps, schema_editor):
    roles = UserRole.view(
        'users/roles_by_domain',
        include_docs=False,
        reduce=False
    ).all()
    for role_doc in iter_docs(UserRole.get_db(), [r['id'] for r in roles]):
        role = UserRole.wrap(role_doc)

        changed = False
        if role.permissions.view_web_apps is not None:
            role.permissions.access_all_apps = role.permissions.view_web_apps
            changed = True
        if role.permissions.view_web_apps_list:
            role.permissions.allowed_app_list = role.permissions.view_web_apps_list
            changed = True
        if changed:
            role.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0023_hqapikey_role_id'),
    ]

    operations = [
        migrations.RunPython(_migrate_web_apps_permissions_to_app_permissions, migrations.RunPython.noop)
    ]
