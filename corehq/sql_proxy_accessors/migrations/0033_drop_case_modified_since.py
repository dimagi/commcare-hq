# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import noop_migration, HqRunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0032_remove_get_cases_by_domain'),
    ]

    operations = [
        HqRunSQL("DROP FUNCTION IF EXISTS case_modified_since(TEXT, TIMESTAMP)")
    ]
