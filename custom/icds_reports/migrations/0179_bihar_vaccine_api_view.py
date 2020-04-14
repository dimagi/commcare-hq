# -*- coding: utf-8 -*-
# Generated on 2020-03-21
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration


migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates', 'database_views'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0178_bihar_vaccine_fields')
    ]

    operations = [
        migrator.get_migration('bihar_vaccine.sql')
    ]
