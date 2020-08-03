# -*- coding: utf-8 -*-
# Generated on 2020-03-21
from __future__ import unicode_literals

from corehq.sql_db.operations import RawSQLMigration
from django.db import migrations

from custom.icds_reports.const import SQL_TEMPLATES_ROOT

migrator = RawSQLMigration((SQL_TEMPLATES_ROOT, 'database_views'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0177_auto_20200408_1837')
    ]

    operations = [
    ]
