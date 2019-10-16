# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-10-16 02:08
from __future__ import unicode_literals

from django.db import migrations

from custom.icds_reports import const

CREATE_INDEX_SQL = "CREATE INDEX CONCURRENTLY IF NOT EXISTS {index} ON {table} ({columns})"
DROP_INDEX_SQL = "DROP INDEX CONCURRENTLY IF EXISTS {index}"


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('icds_reports', '0136_add_infra_field'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL.format(
                index='icds_dashboard_ccs_record_bp_forms_state_id_month_75e9ff13_idx',
                table=const.AGG_CCS_RECORD_BP_TABLE,
                columns=','.join(('state_id', 'month'))
            ),
            reverse_sql=DROP_INDEX_SQL.format(index=''),
            state_operations=[
                migrations.AlterIndexTogether(
                    name='aggregatebirthpreparednesforms',
                    index_together=set([('state_id', 'month')]),
                ),
            ]
        ),
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL.format(
                index='icds_dashboard_ccs_record_cf_forms_state_id_month_4691a220_idx',
                table=const.AGG_COMP_FEEDING_TABLE,
                columns=','.join(('state_id', 'month'))
            ),
            reverse_sql=DROP_INDEX_SQL.format(index=''),
            state_operations=[
                migrations.AlterIndexTogether(
                    name='aggregateccsrecordcomplementaryfeedingforms',
                    index_together=set([('state_id', 'month')]),
                ),
            ]
        ),
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL.format(
                index='icds_dashboard_ccs_recor_state_id_month_9d9fb48f_idx',
                table=const.AGG_CCS_RECORD_BP_TABLE,
                columns=','.join(('state_id', 'month'))
            ),
            reverse_sql=DROP_INDEX_SQL.format(index=''),
            state_operations=[
                migrations.AlterIndexTogether(
                    name='aggregateccsrecorddeliveryforms',
                    index_together=set([('state_id', 'month')]),
                ),
            ]
        ),
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL.format(
                index='icds_dashboard_ccs_recor_state_id_month_4c5045cf_idx',
                table=const.AGG_CCS_RECORD_PNC_TABLE,
                columns=','.join(('state_id', 'month'))
            ),
            reverse_sql=DROP_INDEX_SQL.format(index=''),
            state_operations=[
                migrations.AlterIndexTogether(
                    name='aggregateccsrecordpostnatalcareforms',
                    index_together=set([('state_id', 'month')]),
                ),
            ]
        ),
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL.format(
                index='icds_dashboard_ccs_record_thr_forms_state_id_month_7c1a7acd_idx',
                table=const.AGG_CCS_RECORD_THR_TABLE,
                columns=','.join(('state_id', 'month'))
            ),
            reverse_sql=DROP_INDEX_SQL.format(index=''),
            state_operations=[
                migrations.AlterIndexTogether(
                    name='aggregateccsrecordthrforms',
                    index_together=set([('state_id', 'month')]),
                ),
            ]
        ),
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL.format(
                index='icds_dashboard_child_hea_state_id_month_8d614f3c_idx',
                table=const.AGG_CHILD_HEALTH_PNC_TABLE,
                columns=','.join(('state_id', 'month'))
            ),
            reverse_sql=DROP_INDEX_SQL.format(index=''),
            state_operations=[
                migrations.AlterIndexTogether(
                    name='aggregatechildhealthpostnatalcareforms',
                    index_together=set([('state_id', 'month')]),
                ),
            ]
        ),
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL.format(
                index='icds_dashboard_child_hea_state_id_month_3050cc30_idx',
                table=const.AGG_CHILD_HEALTH_THR_TABLE,
                columns=','.join(('state_id', 'month'))
            ),
            reverse_sql=DROP_INDEX_SQL.format(index=''),
            state_operations=[
                migrations.AlterIndexTogether(
                    name='aggregatechildhealththrforms',
                    index_together=set([('state_id', 'month')]),
                ),
            ]
        ),
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL.format(
                index='icds_dashboard_comp_feed_form_state_id_month_5cf21eec_idx',
                table=const.AGG_COMP_FEEDING_TABLE,
                columns=','.join(('state_id', 'month'))
            ),
            reverse_sql=DROP_INDEX_SQL.format(index=''),
            state_operations=[
                migrations.AlterIndexTogether(
                    name='aggregatecomplementaryfeedingforms',
                    index_together=set([('state_id', 'month')]),
                ),
            ]
        ),
    ]
