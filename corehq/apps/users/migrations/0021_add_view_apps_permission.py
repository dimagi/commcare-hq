from django.db import migrations

from corehq.apps.users.dbaccessors import get_all_role_ids
from dimagi.utils.couch.database import iter_docs

from corehq.apps.users.models import UserRole
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _migrate_view_apps_permission(apps, schema_editor):
    for role_doc in iter_docs(UserRole.get_db(), get_all_role_ids()):
        role = UserRole.wrap(role_doc)

        if role.permissions.edit_apps:
            role.permissions.view_apps = True
            role.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0020_user_staging_pk_to_bigint'),
    ]

    operations = [
        migrations.RunPython(_migrate_view_apps_permission,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True)
    ]
