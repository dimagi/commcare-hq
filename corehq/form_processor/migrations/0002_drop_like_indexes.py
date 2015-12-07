# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0001_squashed_0001_to_0043'),
    ]

    operations = [
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_caseattachmentsql_case_id_2a52028042cc318d_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_caseattachmentsql_name_1d9638e12751b7c9_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xforminstancesql_form_id_60f7da828e471288_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xformattachmentsql_form_id_2c7940ea539d6de4_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xformattachmentsql_name_4b9f1b0d840a70bc_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xformoperationsql_form_id_6610a535ea713665_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_commcarecaseindexs_case_id_7db75a61e418ebfc_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_commcarecasesql_case_id_3dee99b8828d1543_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_casetransaction_case_id_6c13626ba79fe02e_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
    ]
