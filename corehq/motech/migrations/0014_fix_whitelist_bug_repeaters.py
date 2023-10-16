from django.db import migrations

from corehq.motech.migration_utils import repair_repeaters_with_whitelist_bug


def _fix_broken_repeaters(apps, schema_editor):
    repair_repeaters_with_whitelist_bug()


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0013_alter_connectionsettings_auth_type'),
    ]

    operations = [
        migrations.RunPython(_fix_broken_repeaters, migrations.RunPython.noop)
    ]
