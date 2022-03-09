
from django.db import migrations

from dimagi.utils.chunked import chunked
from corehq.apps.users.models_role import SQLPermission, UserRole
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def migrate_edit_migrations_permissions(apps, schema_editor):
    permission, created = SQLPermission.objects.get_or_create(value='edit_messaging')
    edit_data_permission, created = SQLPermission.objects.get_or_create(value='edit_data')
    role_ids_with_edit_data = set(UserRole.objects.filter(rolepermission__permission_fk_id=edit_data_permission.id)
                                  .values_list("id", flat=True))
    for chunk in chunked(role_ids_with_edit_data, 50):
        for role in UserRole.objects.filter(id__in=chunk):
            role.rolepermission_set.get_or_create(permission_fk=permission, defaults={"allow_all": True})


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0036_reset_user_history_records'),
    ]

    operations = [
        migrations.RunPython(migrate_edit_migrations_permissions, migrations.RunPython.noop)
    ]
