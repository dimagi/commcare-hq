# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0025_creditadjustment_permit_blank_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscriber',
            name='domain',
            field=models.CharField(unique=True, max_length=256, db_index=True),
            preserve_default=True,
        ),
    ]
