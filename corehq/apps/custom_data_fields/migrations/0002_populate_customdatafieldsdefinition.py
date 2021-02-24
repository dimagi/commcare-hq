# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.apps.custom_data_fields.management.commands.populate_custom_data_fields import Command


class Migration(migrations.Migration):

    dependencies = [
        ('custom_data_fields', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
