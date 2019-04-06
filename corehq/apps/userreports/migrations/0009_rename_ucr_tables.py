# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations

from corehq.apps.userreports.management.commands.rename_ucr_tables import _rename_tables


def _rename_ucr_tables_migration(apps, schema_editor):
    if not settings.UNIT_TESTING:
        _rename_tables()


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0008_new_table_name_views'),
    ]

    operations = [
        migrations.RunPython(_rename_ucr_tables_migration, migrations.RunPython.noop, elidable=True),
    ]
