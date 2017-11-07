# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0002_vcmmigrationaudit'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='VCMMigrationAudit',
            new_name='VCMMigration',
        ),
    ]
