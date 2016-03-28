# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0009_check_for_domain_default_backend_migration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sqlmobilebackend',
            name='couch_id',
            field=models.CharField(unique=True, max_length=126, db_index=True),
            preserve_default=True,
        ),
    ]
