# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.apps.consumption.management.commands.populate_defaultconsumption import Command


class Migration(migrations.Migration):

    dependencies = [
        ('consumption', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
