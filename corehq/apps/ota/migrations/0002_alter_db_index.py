# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ota', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='demouserrestore',
            name='demo_user_id',
            field=models.CharField(default=None, max_length=255, db_index=True),
            preserve_default=True,
        ),
    ]
