# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0045_casetransaction_sync_log_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecasesql',
            name='owner_id',
            field=models.CharField(max_length=255, null=False),
            preserve_default=True,
        ),
    ]
