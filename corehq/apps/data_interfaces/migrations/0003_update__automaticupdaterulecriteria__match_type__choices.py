# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0002_remove_exists_option'),
    ]

    operations = [
        migrations.AlterField(
            model_name='automaticupdaterulecriteria',
            name='match_type',
            field=models.CharField(max_length=10, choices=[(b'DAYS', b'DAYS'), (b'EQUAL', b'EQUAL'), (b'NOT_EQUAL', b'NOT_EQUAL'), (b'HAS_VALUE', b'HAS_VALUE')]),
            preserve_default=True,
        ),
    ]
