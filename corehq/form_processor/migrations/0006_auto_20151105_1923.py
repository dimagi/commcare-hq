# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import json_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0005_auto_20151105_1556'),
    ]

    operations = [
        migrations.AddField(
            model_name='xforminstancesql',
            name='auth_context',
            field=json_field.fields.JSONField(default='null', help_text='Enter a valid JSON object'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='openrosa_headers',
            field=json_field.fields.JSONField(default='null', help_text='Enter a valid JSON object'),
            preserve_default=True,
        ),
    ]
