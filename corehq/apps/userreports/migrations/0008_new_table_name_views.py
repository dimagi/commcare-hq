# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.userreports.management.commands.rename_ucr_tables import create_ucr_views


def _create_ucr_views_migration(apps, schema_editor):
    create_ucr_views()


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0007_index_indicator_config_ids'),
    ]

    operations = [
        migrations.RunPython(_create_ucr_views_migration, migrations.RunPython.noop, elidable=True),
    ]
