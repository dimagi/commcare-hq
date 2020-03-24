# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.apps.users.management.commands.populate_usersinvitation import Command


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_sqlinvitation'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
