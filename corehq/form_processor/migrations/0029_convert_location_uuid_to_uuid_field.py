# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import djorm_pguuid.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0028_index_location_uuid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecasesql',
            name='location_uuid',
            field=djorm_pguuid.fields.UUIDField(auto_add=False, unique=False, null=True),
            preserve_default=True,
        ),
    ]
