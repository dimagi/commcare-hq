from django.db import migrations

from corehq.apps.users.models_sql import SQLPermission, SQLUserRole
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def migrate_download_reports_permissions(apps, schema_editor):
    new_permission_name = 'download_reports'
    permission, created = SQLPermission.objects.get_or_create(value=new_permission_name)
    for role in SQLUserRole.objects.all().iterator():
        if role.permissions.view_reports or bool(role.permissions.view_report_list):
            rp, created = role.rolepermission_set.get_or_create(permission_fk=permission,
                                                                defaults={"allow_all": True})
            if created:
                role._migration_do_sync()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0030_userhistory_user_upload_record'),
    ]

    operations = [
        migrations.RunPython(migrate_download_reports_permissions, migrations.RunPython.noop)
    ]
