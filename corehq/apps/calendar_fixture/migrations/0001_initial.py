# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CalendarFixtureSettings',
            fields=[
                ('domain', models.CharField(max_length=255, serialize=False, primary_key=True)),
                ('days_before', models.PositiveIntegerField(default=300)),
                ('days_after', models.PositiveIntegerField(default=65)),
            ],
        ),
    ]
