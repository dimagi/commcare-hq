# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='DjangoPillowCheckpoint',
            fields=[
                ('checkpoint_id', models.CharField(max_length=100, serialize=False, primary_key=True)),
                ('sequence', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now=True)),
                ('old_sequence', models.TextField(null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
