# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('commtrack', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockstate',
            name='sql_location',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to='locations.SQLLocation', null=True),
            preserve_default=True,
        ),
    ]
