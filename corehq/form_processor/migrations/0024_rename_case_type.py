# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0023_make_case_name_top_level'),
    ]

    operations = [
        migrations.RenameField(
            model_name='commcarecasesql',
            old_name='case_type',
            new_name='type',
        ),
    ]
