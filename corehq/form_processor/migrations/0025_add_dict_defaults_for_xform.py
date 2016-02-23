# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0024_rename_case_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xforminstancesql',
            name='auth_context',
            field=jsonfield.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='openrosa_headers',
            field=jsonfield.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
            preserve_default=True,
        ),
    ]
