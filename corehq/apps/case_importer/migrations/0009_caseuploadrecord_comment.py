# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0008_caseuploadrecord_task_status_json'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseuploadrecord',
            name='comment',
            field=models.TextField(null=True),
        ),
    ]
