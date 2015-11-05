# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0004_auto_20151105_0018'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='xforminstancesql',
            name='is_archived',
        ),
        migrations.RemoveField(
            model_name='xforminstancesql',
            name='is_deprecated',
        ),
        migrations.RemoveField(
            model_name='xforminstancesql',
            name='is_duplicate',
        ),
        migrations.RemoveField(
            model_name='xforminstancesql',
            name='is_error',
        ),
        migrations.RemoveField(
            model_name='xforminstancesql',
            name='is_submission_error_log',
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=0, choices=[(0, b'normal'), (1, b'archived'), (2, b'deprecated'), (3, b'duplicate'), (4, b'error'), (5, b'submission_error')]),
            preserve_default=True,
        ),
    ]
