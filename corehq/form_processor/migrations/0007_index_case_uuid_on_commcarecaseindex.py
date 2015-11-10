# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0006_commcarecaseindexsql'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.ForeignKey(to='form_processor.CommCareCaseSQL', db_column=b'case_uuid', to_field=b'case_uuid'),
            preserve_default=True,
        ),
    ]
