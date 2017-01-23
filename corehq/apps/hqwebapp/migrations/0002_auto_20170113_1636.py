# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hqwebapp', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='maintenancealert',
            name='modified',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
