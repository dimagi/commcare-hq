# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.core.management import call_command
from corehq.sql_db.operations import HqRunPython


def migrate_translation_transforms(apps, schema_editor):
    call_command('migrate_translation_transforms')


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0001_initial'),
    ]

    operations = [
        HqRunPython(migrate_translation_transforms),
    ]
