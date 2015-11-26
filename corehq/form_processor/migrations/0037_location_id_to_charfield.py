# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0036_standardize_id_field_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecasesql',
            name='location_id',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
    ]
