# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CaseSearchConfig',
            fields=[
                ('domain', models.CharField(max_length=256, serialize=False, primary_key=True, db_index=True)),
                ('enabled', models.BooleanField(default=False)),
                ('_config', jsonfield.fields.JSONField(default={})),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
