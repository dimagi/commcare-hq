# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0021_change_case_forms_related_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecasesql',
            name='case_json',
            field=jsonfield.fields.JSONField(default=dict),
            preserve_default=True,
        ),
    ]
