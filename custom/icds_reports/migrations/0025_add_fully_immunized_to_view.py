# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports',
         '0024_fix_aadhaar_beneficiary_indicator'),
    ]

    operations = [
        migrator.get_migration('create_datasource_views.sql'),
    ]
