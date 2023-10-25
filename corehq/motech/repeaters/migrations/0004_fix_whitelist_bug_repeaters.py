from django.db import migrations

from corehq.motech.repeaters.migration_utils import repair_repeaters_with_whitelist_bug


def _fix_broken_repeaters(apps, schema_editor):
    repair_repeaters_with_whitelist_bug()


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0003_id_fields'),
    ]

    operations = [
        migrations.RunPython(_fix_broken_repeaters, migrations.RunPython.noop)
    ]
