# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.apps.accounting.management.commands.populate_invoicepdf import Command


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0047_create_invoicepdf'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
