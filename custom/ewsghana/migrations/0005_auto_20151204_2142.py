# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ewsghana', '0004_sqlnotification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='facilityincharge',
            name='location',
            field=models.ForeignKey(to='locations.SQLLocation', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
    ]
