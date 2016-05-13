# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0007_smsbillable_multipart_count'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsbillable',
            name='multipart_count',
            field=models.IntegerField(default=1),
            preserve_default=True,
        ),
    ]
