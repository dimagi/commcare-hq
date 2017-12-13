# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0025_add_dict_defaults_for_xform'),
    ]

    operations = [
        migrations.AddField(
            model_name='xforminstancesql',
            name='initial_processing_complete',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
