# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
import json_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),
        ('ilsgateway', '0004_merge'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingReportingDataRecalculation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=128)),
                ('type', models.CharField(max_length=128)),
                ('data', json_field.fields.JSONField(default='null', help_text='Enter a valid JSON object')),
                ('sql_location', models.ForeignKey(to='locations.SQLLocation')),
            ],
            options={
            },
            bases=(models.Model,),
        )
    ]
