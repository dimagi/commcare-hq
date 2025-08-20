from django.db import migrations
from corehq.apps.users.models_role import Permission
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def create_edit_view_tableau_config_permissions(apps, schema_editor):
    Permission.create_all()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0063_rename_location_invitation_primary_location_and_more'),
    ]

    operations = [
        migrations.RunPython(create_edit_view_tableau_config_permissions, migrations.RunPython.noop)
    ]
