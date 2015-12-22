# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('commtrack', '0002_auto_20151204_2142'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockstate',
            name='sql_location',
            field=models.ForeignKey(to='locations.SQLLocation', null=True),
            preserve_default=True,
        ),
    ]
