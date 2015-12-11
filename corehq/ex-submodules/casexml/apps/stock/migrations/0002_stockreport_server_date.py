# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockreport',
            name='server_date',
            field=models.DateTimeField(null=True),
            preserve_default=True,
        ),
    ]
