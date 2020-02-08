# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.apps.api.management.commands.populate_apiuser import Command


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
