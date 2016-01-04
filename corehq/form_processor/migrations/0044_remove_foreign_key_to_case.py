# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0043_rename_to_match'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ledgervalue',
            name='case',
            field=models.CharField(max_length=255, db_index=True),
            preserve_default=True,
        ),
        migrations.RenameField(
            model_name='ledgervalue',
            old_name='case',
            new_name='case_id',
        ),
    ]
