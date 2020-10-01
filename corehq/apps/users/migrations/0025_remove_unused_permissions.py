from django.db import migrations

from dimagi.utils.couch.database import iter_docs

from corehq.apps.toggle_ui.migration_helpers import move_toggles
from corehq.apps.users.models import UserRole
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _remove_webapp_access_permissions(apps, schema_editor):
    roles = UserRole.view(
        'users/roles_by_domain',
        include_docs=False,
        reduce=False
    ).all()
    for role_doc in iter_docs(UserRole.get_db(), [r['id'] for r in roles]):
        role = UserRole.wrap(role_doc)

        changed = False
        if role.permissions.view_web_apps is not None:
            role.permissions.pop('view_web_apps')
            changed = True
        if role.permissions.view_web_apps_list:
            role.permissions.pop('view_web_apps_list')
            changed = True
        if changed:
            role.save()


@skip_on_fresh_install
def migrate_toggles():
    from_toggle_slug = 'role_webapps_permissions'
    to_toggle_slug = 'role_app_access_permissions'
    move_toggles(from_toggle_slug, to_toggle_slug)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0024_add_app_access_permissions'),
    ]

    operations = [
        migrations.RunPython(_remove_webapp_access_permissions, migrations.RunPython.noop),
        migrations.RunPython(migrate_toggles, migrations.RunPython.noop)
    ]
