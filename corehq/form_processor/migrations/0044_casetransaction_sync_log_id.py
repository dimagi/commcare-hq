# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.form_processor.utils.migration import migrate_sql_function


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0043_rename_to_match'),
    ]

    operations = [
        migrations.AddField(
            model_name='casetransaction',
            name='sync_log_id',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
        migrate_sql_function('save_case_and_related_models'),
    ]
