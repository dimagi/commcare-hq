# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


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
