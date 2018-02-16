# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0005_locationtype_include_without_expanding'),
    ]

    operations = [
        migrations.CreateModel(
            name='LocationFixtureConfiguration',
            fields=[
                ('domain', models.CharField(max_length=255, serialize=False, primary_key=True)),
                ('sync_flat_fixture', models.BooleanField(default=True)),
                ('sync_hierarchical_fixture', models.BooleanField(default=True)),
            ],
        ),
    ]
