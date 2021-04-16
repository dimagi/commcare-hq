from django.db import migrations

from dimagi.utils.couch.database import iter_docs

from corehq.apps.users.models import UserRole
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _migrate_edit_reports_permissions(apps, schema_editor):
    roles = UserRole.view(
        'users/roles_by_domain',
        include_docs=False,
        reduce=False
    ).all()
    for role_doc in iter_docs(UserRole.get_db(), [r['id'] for r in roles]):
        role = UserRole.wrap(role_doc)

        changed = False
        if role.permissions.edit_data:
            role.permissions.edit_reports = True
            changed = True
        elif role.permissions.edit_reports:
            role.permissions.edit_reports = False
            changed = True
        if changed:
            role.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0018_auto_20200619_1626'),
    ]

    operations = [
        migrations.RunPython(_migrate_edit_reports_permissions, migrations.RunPython.noop)
    ]
