# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration
from corehq.form_processor.models import XFormInstanceSQL

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0034_update_reindex_functions'),
    ]

    operations = [
        migrator.get_migration('soft_undelete_cases.sql'),
    ]
