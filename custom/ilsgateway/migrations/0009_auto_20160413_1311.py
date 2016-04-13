# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('ilsgateway', '0008_auto_20160401_0807'),
    ]

    operations = [
        migrations.CreateModel(
            name='OneOffTaskProgress',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=128)),
                ('task_name', models.CharField(max_length=128)),
                ('last_synced_object_id', models.CharField(max_length=128, null=True)),
                ('complete', models.BooleanField(default=False)),
                ('progress', models.IntegerField(default=0)),
                ('total', models.IntegerField(default=0)),
            ],
            options={
            },
            bases=(models.Model,),
        )
    ]
