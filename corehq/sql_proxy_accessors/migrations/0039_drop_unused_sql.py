# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-07-03 21:23
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import HqRunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0037_remove_get_extension_case_ids'),
    ]

    operations = [
        HqRunSQL("""DROP FUNCTION IF EXISTS save_ledger_values(
            TEXT, form_processor_ledgervalue, form_processor_ledgertransaction[], TEXT
        )"""),
        HqRunSQL("DROP FUNCTION IF EXISTS hard_delete_forms(TEXT, TEXT[])")
    ]
