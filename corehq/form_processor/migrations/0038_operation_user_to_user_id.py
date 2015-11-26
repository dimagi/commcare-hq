# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0037_location_id_to_charfield'),
    ]

    operations = [
        migrations.RenameField(
            model_name='xformoperationsql',
            old_name='user',
            new_name='user_id',
        ),
    ]
