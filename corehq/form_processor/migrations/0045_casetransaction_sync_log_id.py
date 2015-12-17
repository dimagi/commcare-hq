# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'))

class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0044_remove_foreign_key_to_case'),
    ]

    operations = [
        migrations.AddField(
            model_name='casetransaction',
            name='sync_log_id',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
        migrator.get_migration('save_case_and_related_models.sql'),
    ]
