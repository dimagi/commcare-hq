# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0005_update_http_backend_criteria'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsbillable',
            name='direct_gateway_fee',
            field=models.DecimalField(null=True, max_digits=10, decimal_places=4),
            preserve_default=True,
        ),
    ]
