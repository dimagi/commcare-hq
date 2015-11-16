# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import json_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0024_rename_case_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xforminstancesql',
            name='auth_context',
            field=json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='openrosa_headers',
            field=json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
            preserve_default=True,
        ),
    ]
