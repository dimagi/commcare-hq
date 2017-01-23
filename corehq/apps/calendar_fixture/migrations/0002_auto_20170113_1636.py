# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendar_fixture', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='calendarfixturesettings',
            name='days_after',
            field=models.PositiveIntegerField(default=90),
        ),
    ]
