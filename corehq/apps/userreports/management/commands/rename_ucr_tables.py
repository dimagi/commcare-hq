from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
from collections import defaultdict

import attr
from django.core.management.base import BaseCommand
from django.utils.functional import cached_property
from six.moves import input

from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.sql.util import table_exists, view_exists
from corehq.apps.userreports.util import get_table_name, get_legacy_table_name
from corehq.sql_db.connections import connection_manager
from dimagi.utils.couch.database import iter_docs

logger = logging.getLogger('ucr_rename')


@attr.s
class DSConf(object):
    old_table = attr.ib()
    new_table = attr.ib()
    config = attr.ib()

    @cached_property
    def adapter(self):
        return IndicatorSqlAdapter(self.config)

    @cached_property
    def old_adapter(self):
        return IndicatorSqlAdapter(self.config, self.old_table)


def _run_sql_with_logging(connection, sql, dry_run):
    logger.debug('\t[SQL%s]: %s', ' (dry run)' if dry_run else '', sql)
    if not dry_run:
        connection.execute(sql)


def _table_names(domain, table_id):
    old_table = get_legacy_table_name(domain, table_id)
    new_table = get_table_name(domain, table_id)
    return old_table, new_table


def _get_old_new_tablenames():
    by_engine_id = defaultdict(list)
    seen_tables = defaultdict(set)
    for ds in StaticDataSourceConfiguration.all():
        old, new = _table_names(ds.domain, ds.table_id)
        if old in seen_tables[ds['engine_id']]:
            logger.warning('Duplicate table: %s - %s', ds.get_id, old)
            continue
        seen_tables[ds['engine_id']].add(old)
        by_engine_id[ds['engine_id']].append(DSConf(old, new, ds))

    data_source_ids = [
        row['id']
        for row in DataSourceConfiguration.view(
            'userreports/active_data_sources', reduce=False, include_docs=False
        )
    ]
    for ds in iter_docs(DataSourceConfiguration.get_db(), data_source_ids):
        ds = DataSourceConfiguration.wrap(ds)
        old, new = _table_names(ds.domain, ds.table_id)
        if old in seen_tables[ds['engine_id']]:
            logger.warning('Duplicate table: %s - %s', ds.get_id, old)
            continue
        seen_tables[ds['engine_id']].add(old)
        by_engine_id[ds['engine_id']].append(DSConf(old, new, ds))

    return by_engine_id


def _should_add_view(conn, table_name, view_name):
    return table_exists(conn, table_name) and not view_exists(conn, view_name)


def create_ucr_views(dry_run=False, tables_by_engine=None):
    tables_by_engine = tables_by_engine or _get_old_new_tablenames()
    for engine_id, dsconfs in tables_by_engine.items():
        print('\tChecking {} tables in engine "{}"'.format(len(dsconfs), engine_id))
        engine = connection_manager.get_engine(engine_id)
        view_creates = []
        with engine.begin() as conn:
            for dsconf in dsconfs:
                if _should_add_view(conn, dsconf.old_table, dsconf.new_table):
                    view_creates.append(
                        'CREATE VIEW "{}" AS SELECT * FROM "{}";'.format(dsconf.new_table, dsconf.old_table)
                    )

        if view_creates:
            print('\tCreating {} views in engine "{}"'.format(len(view_creates), engine_id))
            with engine.begin() as conn:
                _run_sql_with_logging(conn, '\n'.join(view_creates), dry_run)
        else:
            print('\tNo views to create in engine "{}"'.format(engine_id))


def _drop_partitioning_features(connection, dsconf, dry_run):
    orm_table = dsconf.old_adapter._get_orm_table_with_partitioning()
    safe_tablename = orm_table.architect.partition.get_partition().safe_tablename
    drop_triggers = """
    DROP TRIGGER IF EXISTS after_insert_{safe_tablename}_trigger on "{parent_table}";
    DROP TRIGGER IF EXISTS before_insert_{safe_tablename}_trigger on "{parent_table}";
    DROP FUNCTION IF EXISTS {safe_tablename}_delete_master();
    DROP FUNCTION IF EXISTS {safe_tablename}_insert_child();
    """.format(safe_tablename=safe_tablename, parent_table=dsconf.old_table)
    print("Dropping partition features for table '{}'".format(dsconf.old_table))
    _run_sql_with_logging(connection, drop_triggers, dry_run)


def _get_child_table_names(connection, parent_table, prefix_match):
    res = connection.execute("""
        SELECT c.relname AS child
        FROM pg_inherits JOIN pg_class AS c ON (inhrelid=c.oid)
        JOIN pg_class as p ON (inhparent=p.oid)
        WHERE p.relname = %(parent_table)s AND c.relname like %(child_prefix)s;
    """, {'parent_table': parent_table, 'child_prefix': '{}%'.format(prefix_match)})

    return [row.child for row in res]


def _rename_child_tables(connection, dsconf, dry_run):
    old_orm_table = dsconf.old_adapter._get_orm_table_with_partitioning()
    old_prefix = old_orm_table.architect.partition.get_partition().safe_tablename
    new_orm_table = dsconf.adapter._get_orm_table_with_partitioning()
    new_prefix = new_orm_table.architect.partition.get_partition().safe_tablename
    child_tables = _get_child_table_names(connection, dsconf.old_table, old_prefix)
    alter_tables = []
    if not child_tables:
        print("No child tables for '{}'".format(dsconf.old_table))
        return

    for table in child_tables:
        suffix = table[len(old_prefix):]
        new_child_table = '{}{}'.format(new_prefix, suffix)
        alter_tables.append('ALTER TABLE "{}" RENAME TO "{}";'.format(table, new_child_table))
    print("Renaming {} child tables of '{}'".format(len(child_tables), dsconf.old_table))
    _run_sql_with_logging(connection, '\n'.join(alter_tables), dry_run)


def _rename_tables(dry_run=False, tables_by_engine=None):
    tables_by_engine = tables_by_engine or _get_old_new_tablenames()
    for engine_id, dsconfs in tables_by_engine.items():
        engine = connection_manager.get_engine(engine_id)
        print('\tChecking {} tables in engine "{}"'.format(len(dsconfs), engine_id))
        for dsconf in dsconfs:
            with engine.begin() as conn:
                old_table_exists = table_exists(conn, dsconf.old_table)
                if old_table_exists:
                    if dsconf.config.sql_settings.partition_config:
                        _drop_partitioning_features(conn, dsconf, dry_run)
                        _rename_child_tables(conn, dsconf, dry_run)

                    drop_view_rename_table = """
                    DROP VIEW IF EXISTS "{new_table}";
                    ALTER TABLE "{old_table}" RENAME TO "{new_table}";
                    """.format(old_table=dsconf.old_table, new_table=dsconf.new_table)

                    print('\t\tRenaming table "{}" to "{}"'.format(dsconf.old_table, dsconf.new_table))
                    _run_sql_with_logging(conn, drop_view_rename_table, dry_run)

            # do this outside the previous transaction to avoid deadlock
            if old_table_exists and dsconf.config.sql_settings.partition_config:
                print('\t\tReinstalling partitioning on "{}"'.format(dsconf.new_table))
                if not dry_run:
                    dsconf.adapter._install_partition()


class Command(BaseCommand):
    help = "Helper for renaming UCR tables"

    def add_arguments(self, parser):
        parser.add_argument('action', choices=('create-views', 'rename-tables'))
        parser.add_argument('--execute', action='store_true', help='Actually run the SQL commands')
        parser.add_argument('--verbose', action='store_true')

    def handle(self, action, **options):
        dry_run = not options['execute']
        if dry_run or options['verbose']:
            logger.setLevel(logging.DEBUG)
            logger.addHandler(logging.StreamHandler())

        def confirm(action):
            return dry_run or input("Are you sure you want to {}? y/n\n".format(action)) == 'y'

        if dry_run:
            print('\nPerforming DRY RUN\n')

        if action == 'create-views':
            # no confirmation needed here since it idempotent and additive
            create_ucr_views(dry_run)

        if action == 'rename-tables' and confirm("rename all UCR tables"):
            _rename_tables(dry_run)
