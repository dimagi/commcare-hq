# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0004_create_commcarecasesql'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecasesql',
            name='case_uuid',
            field=models.CharField(unique=True, max_length=255, db_index=True),
            preserve_default=True,
        ),
    ]
