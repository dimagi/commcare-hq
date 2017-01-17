# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rch', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='rchmother',
            name='MDDS_VillageID',
            field=models.IntegerField(null=True),
        ),
    ]
