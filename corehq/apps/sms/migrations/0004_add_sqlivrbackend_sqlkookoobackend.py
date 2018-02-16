# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0003_add_backend_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='SQLIVRBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlmobilebackend',),
        ),
        migrations.CreateModel(
            name='SQLKooKooBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlivrbackend',),
        ),
    ]
