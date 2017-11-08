# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports',
         '0021_remove_categories'),
    ]

    operations = [
        migrator.get_migration('create_functions.sql'),
    ]
