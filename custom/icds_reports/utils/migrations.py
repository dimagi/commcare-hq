from __future__ import absolute_import
from __future__ import unicode_literals

from django.apps import apps
from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration


def get_view_migrations():
    sql_views = [
        'awc_location_months.sql',
        'awc_location_months_local.sql',
        'agg_awc_monthly.sql',
        'agg_ccs_record_monthly.sql',
        'agg_child_health_monthly.sql',
        'daily_attendance.sql',
        'agg_awc_daily.sql',
        'child_health_monthly.sql',
        'disha_indicators.sql',
        'ccs_record_monthly_view.sql',
        'agg_ls_monthly.sql',
        'service_delivery_monthly.sql',
        'aww_incentive_report_monthly.sql',
    ]
    migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates', 'database_views'))
    operations = []
    for view in sql_views:
        operations.append(migrator.get_migration(view))
    return operations


def _citus_composite_key_sql(model_cls):
    pkey_name = '{}_pkey'.format(model_cls._meta.db_table)
    fields = list(model_cls._meta.unique_together)[0]
    columns = [model_cls._meta.get_field(field).column for field in fields]
    index = '{}_{}_uniq'.format(model_cls._meta.db_table, '_'.join(columns))
    sql = """
        CREATE UNIQUE INDEX {index} on "{table}" ({cols});
        ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS {pkey_name};
        ALTER TABLE "{table}" ADD CONSTRAINT {pkey_name} PRIMARY KEY USING INDEX {index};
    """.format(
        table=model_cls._meta.db_table,
        pkey_name=pkey_name,
        index=index,
        cols=','.join(columns)
    )
    reverse_sql = """
        ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS {index},
        DROP CONSTRAINT IF EXISTS {pkey_name};
        ALTER TABLE "{table}" ADD CONSTRAINT {pkey_name} PRIMARY KEY ({pkey});
        DROP INDEX IF EXISTS {index};
    """.format(
        table=model_cls._meta.db_table,
        pkey_name=pkey_name,
        pkey=model_cls._meta.pk.name,
        index=index,
    )
    if getattr(settings, 'UNIT_TESTING', False):
        return sql, reverse_sql
    else:
        return migrations.RunSQL.noop, reverse_sql


def get_composite_primary_key_migrations(models_to_update):
    operations = []
    for model_name in models_to_update:
        model = apps.get_model('icds_reports', model_name)
        sql, reverse_sql = _citus_composite_key_sql(model)
        operations.append(migrations.RunSQL(
            sql,
            reverse_sql,
            state_operations=[
                migrations.AlterUniqueTogether(
                    name=model_name,
                    unique_together=model._meta.unique_together,
                ),
            ]
        ))
    return operations
