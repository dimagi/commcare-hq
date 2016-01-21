# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('ilsgateway', '0002_auto_20160104_1600'),
    ]

    operations = [
        migrations.CreateModel(
            name='ILSMigrationProblem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=128, db_index=True)),
                ('object_id', models.CharField(max_length=128, null=True)),
                ('object_type', models.CharField(max_length=30)),
                ('description', models.CharField(max_length=128)),
                ('external_id', models.CharField(max_length=128)),
                ('last_modified', models.DateTimeField(auto_now=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ILSMigrationStats',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('products_count', models.IntegerField(default=0)),
                ('locations_count', models.IntegerField(default=0)),
                ('sms_users_count', models.IntegerField(default=0)),
                ('web_users_count', models.IntegerField(default=0)),
                ('domain', models.CharField(max_length=128, db_index=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
            ],
            options={
            },
            bases=(models.Model,),
        )
    ]
