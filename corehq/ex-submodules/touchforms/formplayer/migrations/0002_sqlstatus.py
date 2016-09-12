# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('formplayer', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SqlStatus',
            fields=[
                ('username', models.CharField(max_length=255, serialize=False, primary_key=True)),
                ('app_version', models.IntegerField()),
                ('last_modified', models.DateTimeField(null=True)),
                ('date_created', models.DateTimeField(null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
