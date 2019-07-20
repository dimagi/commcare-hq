# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-07-20 19:16
from __future__ import unicode_literals

from django.db import migrations, models


TABLE_NAME = 'form_processor_casetransaction'
INDEX_NAME = 'form_processor_casetrans_case_id_server_date_sync_f7e3e655_idx'
COLUMNS = ('case_id', 'server_date')

CREATE_INDEX_SQL = "CREATE INDEX CONCURRENTLY IF NOT EXISTS {} ON {} ({})".format(
    INDEX_NAME, TABLE_NAME, ','.join(COLUMNS))
DROP_INDEX_SQL = "DROP INDEX CONCURRENTLY IF EXISTS {}".format(INDEX_NAME)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('form_processor', '0092_add_simplified_transaction_index'),
    ]

    operations = [
        migrations.RunSQL(
            sql=DROP_INDEX_SQL,
            reverse_sql=CREATE_INDEX_SQL,
            state_operations=[
                migrations.AlterIndexTogether(
                    name='casetransaction',
                    index_together=set([('case', 'server_date')]),
                ),
            ]
        )
    ]
