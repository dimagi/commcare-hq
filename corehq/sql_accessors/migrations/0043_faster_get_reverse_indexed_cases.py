# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.form_processor.models import CommCareCaseIndexSQL
from corehq.sql_db.operations import HqRunSQL, RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0042_write_blob_bucket'),
    ]

    operations = [
        migrator.get_migration('get_reverse_indexed_cases_2.sql'),
    ]
