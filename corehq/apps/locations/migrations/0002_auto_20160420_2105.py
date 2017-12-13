# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='locationtype',
            name='_expand_from',
            field=models.ForeignKey(related_name='+', db_column=b'expand_from', to='locations.LocationType', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='locationtype',
            name='_expand_from_root',
            field=models.BooleanField(default=False, db_column=b'expand_from_root'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='locationtype',
            name='expand_to',
            field=models.ForeignKey(related_name='+', to='locations.LocationType', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
