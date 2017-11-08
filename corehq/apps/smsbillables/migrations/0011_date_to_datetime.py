# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0010_gateway_fee_amount_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsbillable',
            name='date_created',
            field=models.DateTimeField(auto_now_add=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='smsbillable',
            name='date_sent',
            field=models.DateTimeField(),
            preserve_default=True,
        ),
    ]
