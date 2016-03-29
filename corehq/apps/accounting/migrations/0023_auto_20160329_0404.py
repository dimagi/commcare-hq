# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from decimal import Decimal
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0022_bootstrap_prbac_roles'),
    ]

    operations = [
        migrations.AlterField(
            model_name='creditline',
            name='balance',
            field=models.DecimalField(default=Decimal('0.0000'), max_digits=10, decimal_places=4, validators=[django.core.validators.MinValueValidator(0)]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creditline',
            name='feature_type',
            field=models.CharField(blank=True, max_length=10, null=True, choices=[(b'User', b'User'), (b'SMS', b'SMS')]),
            preserve_default=True,
        ),
    ]
