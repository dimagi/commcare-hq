# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-10-02 18:27
from __future__ import unicode_literals

from django.db import migrations, models

TABLE_NAME = "icds_dashboard_growth_monitoring_forms"
INDEX_NAME = "icds_dashboard_growth_monitoring_forms_month_59c07619"
COLUMNS = ['month']

CREATE_INDEX_SQL = "CREATE INDEX CONCURRENTLY IF NOT EXISTS {} ON {} ({})".format(
    INDEX_NAME, TABLE_NAME, ','.join(COLUMNS)
)
DROP_INDEX_SQL = "DROP INDEX CONCURRENTLY {}".format(INDEX_NAME)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('icds_reports', '0134_audit_entry_record_response_code'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL,
            reverse_sql=DROP_INDEX_SQL,
            state_operations=[
                migrations.AlterField(
                    model_name='aggregategrowthmonitoringforms',
                    name='month',
                    field=models.DateField(db_index=True, help_text='Will always be YYYY-MM-01'),
                ),
            ]
        ),
    ]
