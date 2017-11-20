# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0020_update_get_ledger_values_for_cases'),
    ]

    operations = [
        noop_migration()
    ]
