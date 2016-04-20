# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0006_remove_smsbillable_api_response'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsbillable',
            name='multipart_count',
            field=models.IntegerField(null=True),
            preserve_default=True,
        ),
    ]
