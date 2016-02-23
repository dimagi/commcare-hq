# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import json_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0048_attachment_content_length_blob_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='xformattachmentsql',
            name='properties',
            field=json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='caseattachmentsql',
            name='attachment_from',
            field=models.TextField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='caseattachmentsql',
            name='properties',
            field=json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='caseattachmentsql',
            name='attachment_src',
            field=models.TextField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='caseattachmentsql',
            name='identifier',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
    ]
