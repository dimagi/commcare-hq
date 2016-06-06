# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import HqRunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0024_get_case_ids_in_domain'),
    ]

    operations = [
        HqRunSQL(
            "DROP FUNCTION IF EXISTS get_ledger_values_for_product_ids(TEXT[])",
            "SELECT 1"
        ),
    ]
