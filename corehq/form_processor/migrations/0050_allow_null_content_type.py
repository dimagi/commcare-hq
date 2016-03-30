# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0049_case_attachment_props'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='content_type',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='content_type',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
    ]
