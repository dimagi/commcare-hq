from django.db import migrations

from corehq.apps.users.models_role import SQLPermission
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def create_release_management_permission(apps, schema_editor):
    SQLPermission.objects.get_or_create(value='access_release_management')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0042_deactivatemobileworkertrigger'),
    ]

    operations = [
        migrations.RunPython(create_release_management_permission, migrations.RunPython.noop)
    ]
