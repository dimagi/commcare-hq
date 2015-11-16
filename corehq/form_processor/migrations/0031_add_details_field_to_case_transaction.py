# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import json_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0030_casetransaction_revoked'),
    ]

    operations = [
        migrations.AddField(
            model_name='casetransaction',
            name='details',
            field=json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, b'form'), (1, b'rebuild_with_reason'), (2, b'user_requested_rebuild'), (3, b'user_archived_rebuild'), (4, b'form_archive_rebuild'), (5, b'form_edit_rebuild')]),
            preserve_default=True,
        ),
    ]
