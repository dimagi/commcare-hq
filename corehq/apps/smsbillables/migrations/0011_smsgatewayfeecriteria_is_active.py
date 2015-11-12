# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0010_gateway_fee_amount_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsgatewayfeecriteria',
            name='is_active',
            field=models.BooleanField(default=True, db_index=True),
            preserve_default=True,
        ),
    ]
