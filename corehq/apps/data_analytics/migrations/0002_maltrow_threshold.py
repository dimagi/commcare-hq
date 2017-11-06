# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0001_squashed_0004_auto_20150810_1710'),
    ]

    operations = [
        migrations.AddField(
            model_name='maltrow',
            name='threshold',
            field=models.PositiveSmallIntegerField(default=15),
            preserve_default=True,
        ),
    ]
