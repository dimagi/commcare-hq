from django.db import migrations

from corehq.apps.domain.management.commands.populate_messagingsettings import (
    Command,
)


def _migrate_from_migration(apps, schema_editor):
    Command.migrate_from_migration(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0012_messagingsettings'),
    ]

    operations = [
        migrations.RunPython(_migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
