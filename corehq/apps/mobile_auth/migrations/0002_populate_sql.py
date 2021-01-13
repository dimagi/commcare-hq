# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.apps.mobile_auth.management.commands.populate_mobileauthkeyrecord import Command


class Migration(migrations.Migration):

    dependencies = [
        ('mobile_auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
