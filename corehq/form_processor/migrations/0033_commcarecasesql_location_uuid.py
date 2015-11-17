# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0032_change_transaction_related_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='commcarecasesql',
            name='location_uuid',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
    ]
