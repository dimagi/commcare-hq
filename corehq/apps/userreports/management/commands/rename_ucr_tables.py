from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from collections import defaultdict

from django.core.management import CommandError
from django.core.management.base import BaseCommand
from six.moves import input

from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
from corehq.apps.userreports.sql.util import table_exists, view_exists
from corehq.apps.userreports.util import get_table_name, get_legacy_table_name
from corehq.sql_db.connections import connection_manager
from dimagi.utils.couch.database import iter_docs


def _table_names(domain, table_id):
    old_table = get_legacy_table_name(domain, table_id)
    new_table = get_table_name(domain, table_id)
    return old_table, new_table


def _get_old_new_tablenames():
    data_source_ids = [
        row['id']
        for row in DataSourceConfiguration.view(
            'userreports/active_data_sources', reduce=False, include_docs=False
        )
    ]
    by_engine_id = defaultdict(list)
    for ds in iter_docs(DataSourceConfiguration.get_db(), data_source_ids):
        by_engine_id[ds['engine_id']].append(_table_names(ds['domain'], ds['table_id']))

    for ds in StaticDataSourceConfiguration.all():
        by_engine_id[ds['engine_id']].append(_table_names(ds['domain'], ds['table_id']))

    return by_engine_id


def _should_add_view(conn, table_name, view_name):
    return table_exists(conn, table_name) and not view_exists(conn, view_name)


def create_ucr_views():
    tables_by_engine = _get_old_new_tablenames()
    for engine_id, tables in tables_by_engine.items():
        print('\tChecking {} tables in engine "{}"'.format(len(tables), engine_id))
        engine = connection_manager.get_engine(engine_id)
        view_creates = []
        with engine.begin() as conn:
            for old_table, new_table in tables:
                if _should_add_view(conn, old_table, new_table):
                    view_creates.append('CREATE VIEW "{}" AS SELECT * FROM "{}";'.format(new_table, old_table))

        if view_creates:
            print('\tCreating {} views in engine "{}"'.format(len(view_creates), engine_id))
            with engine.begin() as conn:
                conn.execute('\n'.join(view_creates))
        else:
            print('\tNo views to create in engine "{}"'.format(engine_id))


def _rename_tables():
    tables_by_engine = _get_old_new_tablenames()
    for engine_id, tables in tables_by_engine.items():
        engine = connection_manager.get_engine(engine_id)
        print('\tChecking {} tables in engine "{}"'.format(len(tables), engine_id))
        for old_table, new_table in tables:
            drop_view_rename_table = """
            DROP VIEW IF EXISTS "{new_table}";
            ALTER TABLE "{old_table}" RENAME TO "{new_table}";
            """.format(old_table=old_table, new_table=new_table)
            with engine.begin() as conn:
                if table_exists(conn, old_table):
                    print('\t\tRenaming table "{}" to "{}"'.format(old_table, new_table))
                    conn.execute(drop_view_rename_table)


class Command(BaseCommand):
    help = "Helper for renaming UCR tables"

    def add_arguments(self, parser):
        parser.add_argument('--create-views', action='store_true', default=False)
        parser.add_argument('--rename-tables', action='store_true', default=False)

    def handle(self, create_views, rename_tables, **options):
        if sum([create_views, rename_tables]) != 1:
            raise CommandError("Exactly one action argument must be given.")

        def confirm(action):
            return input("Are you sure you want to {}? y/n\n".format(action)) == 'y'

        if create_views:
            # no confirmation needed here since it idempotent and additive
            create_ucr_views()

        if rename_tables and confirm("rename all UCR tables"):
            _rename_tables()
