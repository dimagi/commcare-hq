# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0004_auto_20160914_2030'),
    ]

    operations = [
        migrations.AddField(
            model_name='locationtype',
            name='_include_root_without_expanding',
            field=models.BooleanField(default=False, db_column=b'include_root_without_expanding'),
        ),
        migrations.AddField(
            model_name='locationtype',
            name='_include_without_expanding',
            field=models.ForeignKey(related_name='+', db_column=b'include_without_expanding', to='locations.LocationType', null=True),
        ),
    ]
