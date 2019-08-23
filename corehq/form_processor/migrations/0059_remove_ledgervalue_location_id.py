# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0058_update_indexes'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ledgervalue',
            name='location_id',
        ),
    ]
