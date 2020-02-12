# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.apps.registration.management.commands.populate_sql_registration_request import Command


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
