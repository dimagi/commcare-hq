from django.db import migrations

from corehq.apps.users.models_role import Permission


def create_release_management_permission(apps, schema_editor):
    Permission.create_all()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0042_deactivatemobileworkertrigger'),
    ]

    operations = [
        migrations.RunPython(create_release_management_permission, migrations.RunPython.noop)
    ]
