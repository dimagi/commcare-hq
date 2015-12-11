# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TimezoneMigrationProgress',
            fields=[
                ('domain', models.CharField(max_length=256, serialize=False, primary_key=True, db_index=True)),
                ('migration_status', models.CharField(default=b'not_started', max_length=11, choices=[(b'not_started', b'Not Started'), (b'in_progress', b'In Progress'), (b'complete', b'Complete')])),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
