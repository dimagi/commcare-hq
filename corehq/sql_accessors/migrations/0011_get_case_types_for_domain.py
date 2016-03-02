# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.form_processor.models import CaseTransaction, XFormInstanceSQL, CommCareCaseIndexSQL, XFormOperationSQL
from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0010_update_state_type_values'),
    ]

    operations = [
        migrator.get_migration('get_case_types_for_domain.sql'),
    ]
