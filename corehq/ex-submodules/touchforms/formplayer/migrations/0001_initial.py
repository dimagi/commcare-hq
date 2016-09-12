# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EntrySession',
            fields=[
                ('session_id', models.CharField(max_length=100, serialize=False, primary_key=True)),
                ('form', models.CharField(max_length=255)),
                ('app_id', models.CharField(max_length=32, null=True, blank=True)),
                ('session_name', models.CharField(max_length=100)),
                ('created_date', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('last_activity_date', models.DateTimeField(null=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Session',
            fields=[
                ('sess_id', models.CharField(max_length=100, serialize=False, primary_key=True)),
                ('sess_json', models.TextField()),
                ('last_modified', models.DateTimeField(null=True)),
                ('date_created', models.DateTimeField(null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='XForm',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('name', models.CharField(max_length=255)),
                ('namespace', models.CharField(max_length=255)),
                ('version', models.IntegerField(null=True)),
                ('uiversion', models.IntegerField(null=True)),
                ('checksum', models.CharField(help_text=b'Attachment SHA-1 Checksum', max_length=40, blank=True)),
                ('file', models.FileField(max_length=255, upload_to=b'xforms')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
