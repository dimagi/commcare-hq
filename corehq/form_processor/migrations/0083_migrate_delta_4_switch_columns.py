# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration


migrator = RawSQLMigration(('corehq', 'form_processor', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0082_migrate_delta_3_backfill_notnull'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrator.get_migration('migrate_delta_4_switch_columns.sql'),
            ]
        ),
    ]
