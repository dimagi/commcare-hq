# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0015_change_related_names_for_form_attachment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='attachment_uuid',
            field=models.CharField(unique=True, max_length=255, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='name',
            field=models.CharField(max_length=255, db_index=True),
            preserve_default=True,
        ),
    ]
