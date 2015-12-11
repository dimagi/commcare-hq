# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='maltrow',
            name='user_type',
            field=models.TextField(),
            preserve_default=False,
        ),
    ]
