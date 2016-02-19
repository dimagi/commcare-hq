# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0005_add_fields_to_attachments'),
    ]

    operations = [
        migrator.get_migration('save_case_and_related_models.sql'),
        migrator.get_migration('save_new_form_and_related_models.sql'),
    ]
