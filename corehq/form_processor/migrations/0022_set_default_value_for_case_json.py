# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import json_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0021_change_case_forms_related_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecasesql',
            name='case_json',
            field=json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
            preserve_default=True,
        ),
    ]
