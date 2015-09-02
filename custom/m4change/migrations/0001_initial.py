# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='McctStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_id', models.CharField(unique=True, max_length=100, db_index=True)),
                ('status', models.CharField(max_length=20)),
                ('domain', models.CharField(max_length=256, null=True, db_index=True)),
                ('reason', models.CharField(max_length=32, null=True)),
                ('received_on', models.DateField(null=True)),
                ('registration_date', models.DateField(null=True)),
                ('immunized', models.BooleanField(default=False)),
                ('is_booking', models.BooleanField(default=False)),
                ('is_stillbirth', models.BooleanField(default=False)),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('user', models.CharField(max_length=255, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
