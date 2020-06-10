from django.db import migrations

from dimagi.utils.couch.database import iter_docs

from corehq.apps.users.models import UserRole
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _migrate_web_apps_permissions(apps, schema_editor):
    roles = UserRole.view(
        'users/roles_by_domain',
        include_docs=False,
        reduce=False
    ).all()
    for role_doc in iter_docs(UserRole.get_db(), [r['id'] for r in roles]):
        role = UserRole.wrap(role_doc)

        changed = False
        if role.permissions.edit_data:
            role.permissions.access_web_apps = True
            changed = True
        elif role.permissions.access_web_apps:
            role.permissions.access_web_apps = False
            changed = True
        if changed:
            role.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0015_domainpermissionsmirror'),
    ]

    operations = [
        migrations.RunPython(_migrate_web_apps_permissions)
    ]
