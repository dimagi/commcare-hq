# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0017_problem_to_text_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='xforminstancesql',
            name='user_id',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
    ]
