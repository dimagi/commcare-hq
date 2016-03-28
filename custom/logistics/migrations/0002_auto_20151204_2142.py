# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('logistics', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockdatacheckpoint',
            name='location',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, blank=True, to='locations.SQLLocation', null=True),
            preserve_default=True,
        ),
    ]
