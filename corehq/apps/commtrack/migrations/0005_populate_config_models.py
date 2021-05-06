# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.apps.commtrack.management.commands.populate_commtrackconfig import Command


class Migration(migrations.Migration):

    dependencies = [
        ('commtrack', '0004_update_overstock_threshold'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
