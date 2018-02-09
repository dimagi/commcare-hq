# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0006_esrestorepillowcheckpoints'),
    ]

    operations = [
        migrations.AlterField(
            model_name='esrestorepillowcheckpoints',
            name='date_updated',
            field=models.DateField(),
        ),
    ]
