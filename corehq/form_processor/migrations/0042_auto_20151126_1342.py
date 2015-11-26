# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0041_auto_20151126_1339'),
    ]

    operations = [
        migrations.RenameField(
            model_name='xformoperationsql',
            old_name='user',
            new_name='user_id',
        ),
    ]
