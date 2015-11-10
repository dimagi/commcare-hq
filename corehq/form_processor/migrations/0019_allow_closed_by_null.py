# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0018_xforminstancesql_user_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecasesql',
            name='closed_by',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
    ]
