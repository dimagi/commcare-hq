# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0048_attachment_content_length_blob_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='xformattachmentsql',
            name='properties',
            field=jsonfield.fields.JSONField(default=dict),
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
            field=jsonfield.fields.JSONField(default=dict),
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
