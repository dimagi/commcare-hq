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
                ('token', models.CharField(unique=True, max_length=126, db_index=True)),
                ('app_id', models.CharField(max_length=126, null=True)),
                ('expiration_date', models.DateField()),
                ('created_date', models.DateTimeField()),
                ('odk_url', models.CharField(max_length=126, null=True)),
                ('phone_type', models.CharField(max_length=20, null=True, choices=[(b'android', 'Android'), (b'other', 'Other')])),
                ('registered_date', models.DateTimeField(null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
