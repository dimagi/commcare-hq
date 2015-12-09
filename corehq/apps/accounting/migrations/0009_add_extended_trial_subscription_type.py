# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0008_auto_20151120_1652'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='service_type',
            field=models.CharField(default=b'NOT_SET', max_length=25, choices=[(b'IMPLEMENTATION', b'Implementation'), (b'PRODUCT', b'Product'), (b'TRIAL', b'Trial'), (b'EXTENDED_TRIAL', b'Extended Trial'), (b'SANDBOX', b'Sandbox'), (b'INTERNAL', b'Internal')]),
            preserve_default=True,
        ),
    ]
