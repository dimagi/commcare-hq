from __future__ import absolute_import
from __future__ import print_function

from alembic.operations import Operations
from django.core.management.base import BaseCommand
from sqlalchemy import Index

from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain, get_app
from corehq.apps.app_manager.models import ReportModule
from corehq.apps.userreports.models import get_datasource_config
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.sql.adapter import _custom_index_name
from corehq.apps.userreports.sql.columns import column_to_sql
from corehq.apps.userreports.util import get_table_name
from fluff.signals import get_migration_context

DEID_FIELDS = [
    "aadhar_number",
    "add",
    "awc_name",
    "bank_account_number",
    "contact_phone_number",
    "date_death",
    "date_last_private_admit",
    "date_primary_admit",
    "dimagi_username",
    "edd",
    "email",
    "helpdesk_phone_number",
    "hh_gps_location",
    "ls_name",
    "ls_phone_number",
    "mcp_id",
    "mcts_id",
    "mother_name",
    "name",
    "person_name",
    "phone_number",
    "raw_aadhar_string",
    "rch_id",
    "referral_reached_date",
    "resident",
    "supervisor_name",
    "time_birth",
]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        apps_in_domain = get_app_ids_in_domain(domain)
        data_source_ids = set()
        for app_id in apps_in_domain:
            app = get_app(domain, app_id)
            for module in app.get_modules():
                if isinstance(module, ReportModule):
                    for report in module.reports:
                        data_source_ids.add(report.config_id)

        for ds_id in data_source_ids:
            ds = get_datasource_config(ds_id, domain)[0]
            table_name = get_table_name(ds.domain, ds.table_id)
            ds_deid_columns = []
            for column in ds.get_columns():
                if column.database_column_name in DEID_FIELDS:
                    if column.is_primary_key:
                        print("Won't update '%s.%s' since its a primary key" % (
                            table_name, column.database_column_name
                        ))
                    else:
                        ds_deid_columns.append(column)

            if ds_deid_columns:
                adapter = IndicatorSqlAdapter(ds)
                engine = adapter.engine
                table = adapter.get_table()
                with engine.begin() as conn:
                    ctx = get_migration_context(conn, [table_name])
                    op = Operations(ctx)
                    for col in ds_deid_columns:
                        sql_col = column_to_sql(col)
                        sql_col.nullable = True
                        print('Dropping and adding column %s.%s' % (
                            table_name, col.database_column_name
                        ))
                        op.drop_column(table_name, col.database_column_name)
                        op.add_column(table_name, sql_col)

                        if col.create_index:
                            print("WARNING: index for column '%s.%s' may need to be re-created" % (
                                table_name, col.database_column_name
                            ))

                for index in ds.sql_column_indexes:
                    rebuild_index = set(index.column_ids).intersection({
                        col.database_column_name for col in ds_deid_columns
                    })
                    if rebuild_index:
                        sql_index = Index(
                            _custom_index_name(table_name, index.column_ids),
                            *index.column_ids
                        )
                        sql_index._set_parent(table)
                        print('Creating index on %s: %s' % (table_name, sql_index))
                        sql_index.create(engine)
