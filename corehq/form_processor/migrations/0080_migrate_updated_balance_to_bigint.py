# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations, models

from corehq.sql_db.operations import RawSQLMigration


migrator = RawSQLMigration(('corehq', 'form_processor', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0079_migrate_delta_to_bigint'),
    ]

    operations = [
        migrator.get_migration('migrate_updated_balance_to_bigint.sql'),
        migrations.SeparateDatabaseAndState(state_operations=[
            migrations.AlterField(
                model_name='ledgertransaction',
                name='updated_balance',
                field=models.BigIntegerField(),
            ),
        ]),
    ]
