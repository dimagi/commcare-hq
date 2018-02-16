# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import HqRunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0030_index_changes'),
    ]

    operations = [
        HqRunSQL(
            "DROP FUNCTION IF EXISTS get_ledger_values_for_product_ids(TEXT[])",
            "SELECT 1"
        ),
    ]
