# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0017_allow_closed_by_null'),
    ]

    operations = [
        migrations.RenameField(
            model_name='commcarecaseindexsql',
            old_name='relationship',
            new_name='relationship_id',
        ),
    ]
