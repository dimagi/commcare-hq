from django.db import migrations

from corehq.apps.builds.management.commands.populate_commcarebuild import Command


class Migration(migrations.Migration):

    dependencies = [
        ('builds', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
