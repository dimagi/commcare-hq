# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0038_attachment_bucket'),
    ]

    operations = [
        migrator.get_migration('save_case_and_related_models_2.sql'),
    ]
