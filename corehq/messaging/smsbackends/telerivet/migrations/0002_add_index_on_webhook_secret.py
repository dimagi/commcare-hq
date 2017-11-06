# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('telerivet', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='incomingrequest',
            name='secret',
            field=models.CharField(max_length=255, null=True, db_index=True),
            preserve_default=True,
        ),
    ]
