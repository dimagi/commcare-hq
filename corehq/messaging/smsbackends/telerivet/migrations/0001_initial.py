# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='IncomingRequest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('event', models.CharField(max_length=255, null=True)),
                ('message_id', models.CharField(max_length=255, null=True)),
                ('message_type', models.CharField(max_length=255, null=True)),
                ('content', models.TextField(null=True)),
                ('from_number', models.CharField(max_length=255, null=True)),
                ('from_number_e164', models.CharField(max_length=255, null=True)),
                ('to_number', models.CharField(max_length=255, null=True)),
                ('time_created', models.CharField(max_length=255, null=True)),
                ('time_sent', models.CharField(max_length=255, null=True)),
                ('contact_id', models.CharField(max_length=255, null=True)),
                ('phone_id', models.CharField(max_length=255, null=True)),
                ('service_id', models.CharField(max_length=255, null=True)),
                ('project_id', models.CharField(max_length=255, null=True)),
                ('secret', models.CharField(max_length=255, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
