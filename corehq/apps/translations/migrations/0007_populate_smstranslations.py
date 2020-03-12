# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.apps.translations.management.commands.populate_smstranslations import Command


class Migration(migrations.Migration):

    dependencies = [
        ('translations', '0006_add_smstranslations'),
    ]

    operations = [
        migrations.RunPython(Command.migrate_from_migration,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
