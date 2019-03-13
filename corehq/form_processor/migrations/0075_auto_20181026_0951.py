# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-10-26 09:51
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations



TABLE_NAME = 'form_processor_commcarecasesql'
INDEX_NAME = 'form_processor_commcarecasesql_domain_type_05e599e0_idx'
COLUMNS = ['domain', 'type']

CREATE_INDEX_SQL = "CREATE INDEX CONCURRENTLY {} ON {} ({})".format(
    INDEX_NAME, TABLE_NAME, ','.join(COLUMNS))
DROP_INDEX_SQL = "DROP INDEX CONCURRENTLY {}".format(INDEX_NAME)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('form_processor', '0074_casetransaction__client_date'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL,
            reverse_sql=DROP_INDEX_SQL,
            state_operations=[
                migrations.AlterIndexTogether(
                    name='commcarecasesql',
                    index_together=set([
                        ('owner_id', 'server_modified_on'),
                        ('domain', 'owner_id', 'closed'),
                        ('domain', 'external_id', 'type'),
                        ('domain', 'type')
                    ]),
                ),
            ]
        ),
    ]
