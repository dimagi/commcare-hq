# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0007_auto_20161209_2004'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseuploadrecord',
            name='task_status_json',
            field=jsonfield.fields.JSONField(null=True),
        ),
    ]
