# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0012_remove_max_length'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsbillable',
            name='domain',
            field=models.CharField(max_length=100, db_index=True),
            preserve_default=True,
        ),
    ]
