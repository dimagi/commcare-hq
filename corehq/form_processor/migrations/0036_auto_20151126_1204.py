# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0035_remove_varchar_pattern_ops_indexes'),
    ]

    operations = [
        migrations.RenameField(
            model_name='xformattachmentsql',
            old_name='xform',
            new_name='form',
        ),
        migrations.RenameField(
            model_name='xformoperationsql',
            old_name='xform',
            new_name='form',
        ),
    ]
