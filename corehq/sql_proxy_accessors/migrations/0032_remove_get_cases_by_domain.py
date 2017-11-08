# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import noop_migration, HqRunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0031_write_blob_bucket'),
    ]

    operations = [
        HqRunSQL("DROP FUNCTION IF EXISTS get_case_types_for_domain(TEXT)")
    ]
