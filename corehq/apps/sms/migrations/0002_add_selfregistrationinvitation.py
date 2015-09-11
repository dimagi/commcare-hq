# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SelfRegistrationInvitation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=126, db_index=True)),
                ('phone_number', models.CharField(max_length=30, db_index=True)),
                ('token', models.CharField(max_length=126, db_index=True)),
                ('app_id', models.CharField(max_length=126, null=True)),
                ('expiration_dt', models.DateField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
