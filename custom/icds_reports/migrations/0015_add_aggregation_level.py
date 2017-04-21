# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0014_add_datasource_views'),
    ]

    operations = [
        migrator.get_migration('update_tables8.sql'),
        migrator.get_migration('create_datasource_views.sql'),
        migrator.get_migration('create_functions.sql'),
    ]
