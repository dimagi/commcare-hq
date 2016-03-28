# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import models, migrations

from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})

class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0004_get_modified_since_functions'),
    ]

    operations = [
        HqRunSQL(
            "DROP FUNCTION IF EXISTS get_case_attachment_by_name(TEXT, TEXT)",
            "SELECT 1"
        ),
        migrator.get_migration('get_case_attachment_by_identifier.sql'),
    ]
