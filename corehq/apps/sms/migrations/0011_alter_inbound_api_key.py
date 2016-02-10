# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0010_update_sqlmobilebackend_couch_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sqlmobilebackend',
            name='inbound_api_key',
            field=models.CharField(unique=True, max_length=126, db_index=True),
            preserve_default=True,
        ),
    ]
