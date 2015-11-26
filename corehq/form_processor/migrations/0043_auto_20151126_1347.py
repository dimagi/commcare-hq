# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0042_auto_20151126_1342'),
    ]

    operations = [
        migrations.RenameField(
            model_name='commcarecasesql',
            old_name='location_uuid',
            new_name='location_id',
        ),
    ]
