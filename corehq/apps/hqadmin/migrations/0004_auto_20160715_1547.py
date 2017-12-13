# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0003_auto_20160715_1543'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vcmmigration',
            name='migrated',
            field=models.DateTimeField(null=True),
            preserve_default=True,
        ),
    ]
