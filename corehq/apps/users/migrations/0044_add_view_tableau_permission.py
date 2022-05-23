from django.db import migrations

from corehq.apps.users.models_role import SQLPermission


def create_view_tableau_permission(apps, schema_editor):
    SQLPermission.create_all()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0043_add_release_management_permission'),
    ]

    operations = [
        migrations.RunPython(create_view_tableau_permission, migrations.RunPython.noop)
    ]
