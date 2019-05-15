from __future__ import absolute_import
from __future__ import unicode_literals

from django.apps import apps
from django.conf import settings
from django.db import migrations, router

from corehq.sql_db.connections import is_citus_db
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
    return sql, reverse_sql


class OnlyCitusRunSql(migrations.RunSQL):
    """Only run the SQL if the database is CitusDB"""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if (
            router.allow_migrate(schema_editor.connection.alias, app_label, **self.hints)
            and (settings.UNIT_TESTING or self._is_citus(schema_editor))
        ):
            self._run_sql(schema_editor, self.sql)

    def _is_citus(self, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            return is_citus_db(cursor)


def get_composite_primary_key_migrations(models_to_update):
    operations = []
    for model_name in models_to_update:
        model = apps.get_model('icds_reports', model_name)
        sql, reverse_sql = _citus_composite_key_sql(model)
        operations.append(OnlyCitusRunSql(
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


def create_citus_distributed_table(connection, table, distribution_column):
    res = connection.execute("""
        select 1 from pg_dist_partition
        where partmethod = 'h' and logicalrelid = %s::regclass
    """, [table])
    if res is None:
        res = list(connection)
    if not list(res):
        connection.execute("select create_distributed_table(%s, %s)", [table, distribution_column])


def create_citus_reference_table(connection, table):
    res = connection.execute("""
        select 1 from pg_dist_partition
        where partmethod = 'n' and logicalrelid = %s::regclass
    """, [table])
    if res is None:
        res = list(connection)
    if not list(res):
        connection.execute("select create_reference_table(%s)", [table])
