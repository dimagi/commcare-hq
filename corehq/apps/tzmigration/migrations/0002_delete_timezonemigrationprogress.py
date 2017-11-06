# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tzmigration', '0001_initial'),
        ('domain_migration_flags', '0002_migrate_data_from_tzmigration'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TimezoneMigrationProgress',
        ),
    ]
