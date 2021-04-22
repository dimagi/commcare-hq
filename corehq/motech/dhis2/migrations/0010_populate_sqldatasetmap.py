from django.db import migrations

from corehq.motech.dhis2.management.commands.populate_sqldatasetmap import (
    Command,
)


def _migrate_from_migration(apps, schema_editor):
    Command.migrate_from_migration(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ('dhis2', '0009_sqldatasetmap_sqldatavaluemap'),
    ]

    operations = [
        migrations.RunPython(_migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
