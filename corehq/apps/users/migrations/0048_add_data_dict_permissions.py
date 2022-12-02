import traceback
from django.db import migrations

from django.core.management import call_command
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def migrate_data_dict_permissions(apps, schema_editor):
    try:
        call_command(
            "add_data_dict_permissions",
        )
    except Exception:
        traceback.print_exc()

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0047_rename_sqlpermission_permission'),
    ]

    operations = [
        migrations.RunPython(migrate_data_dict_permissions, migrations.RunPython.noop)
    ]
