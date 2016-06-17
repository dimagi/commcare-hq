# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='DemoUserRestore',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('demo_user_id', models.CharField(default=None, max_length=255, db_index=True)),
                ('restore_blob_id', models.CharField(default=None, max_length=255)),
                ('content_length', models.IntegerField(null=True)),
                ('timestamp_created', models.DateTimeField(auto_now=True)),
                ('restore_comment', models.CharField(max_length=250, null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
