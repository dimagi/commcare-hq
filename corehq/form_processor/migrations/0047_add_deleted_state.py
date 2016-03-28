# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0046_add_not_null_constraint_to_owner_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=0, choices=[(0, b'normal'), (1, b'archived'), (2, b'deprecated'), (4, b'duplicate'), (8, b'error'), (16, b'submission_error'), (32, b'deleted')]),
            preserve_default=True,
        ),
    ]
