# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0016_index_case_attachment_uuid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xforminstancesql',
            name='problem',
            field=models.TextField(null=True),
            preserve_default=True,
        ),
    ]
