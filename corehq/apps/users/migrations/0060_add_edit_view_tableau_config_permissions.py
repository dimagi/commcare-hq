from django.db import migrations
from corehq.apps.users.models_role import Permission


def create_edit_view_tableau_config_permissions(apps, schema_editor):
    Permission.create_all()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0059_invitations_addtableau_roles_and_groupids'),
    ]

    operations = [
        migrations.RunPython(create_edit_view_tableau_config_permissions, migrations.RunPython.noop)
    ]
