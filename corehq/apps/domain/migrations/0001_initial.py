# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TransferDomainRequest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('active', models.BooleanField(default=True)),
                ('request_time', models.DateTimeField(null=True, blank=True)),
                ('request_ip', models.CharField(max_length=80, null=True, blank=True)),
                ('confirm_time', models.DateTimeField(null=True, blank=True)),
                ('confirm_ip', models.CharField(max_length=80, null=True, blank=True)),
                ('transfer_guid', models.CharField(max_length=32, null=True, blank=True)),
                ('domain', models.CharField(max_length=256)),
                ('from_username', models.CharField(max_length=80)),
                ('to_username', models.CharField(max_length=80)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
