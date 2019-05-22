from __future__ import absolute_import, print_function
from __future__ import unicode_literals, division

import argparse
import logging
import sqlite3
import subprocess
import sys
from datetime import datetime
from time import sleep

from six.moves import input

logger = logging.getLogger(__name__)


def parse_date(s, default=None):
    if not s:
        return default

    try:
        return datetime.strptime(s, "%Y-%m-%d").date().replace(day=1)
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


class Database(object):
    def __init__(self, db_path):
        self.db_path = db_path

    def execute(self, query, *params):
        with self.db:
            res = self.db.execute(query, params)
            return res.fetchall()

    def get_table(self, table_name):
        rows = self.execute('select * from tables where source_table = ?', table_name)
        if not rows:
            raise Exception('No table found with name "{}"'.format(table_name))

        row = rows[0]
        if row['migrated']:
            raise Exception('Table "{}" has already been migrated'.format(table_name))

        return row['source_table'], row['target_table']

    def get_tables(self, start_date=None, end_date=None):
        params = []
        filters = []
        if start_date and end_date:
            filters.append('date is not null')

        if start_date:
            if not end_date:
                filters.append("date is null OR date >= ?")
            else:
                filters.append("date >= ?")
            params.append(start_date)

        if end_date:
            filters.append("date < ?")
            params.append(end_date)

        query = 'SELECT * FROM tables WHERE migrated is null'
        if filters:
            query += ' and ({})'.format(' and '.join(filters))
        return [
            (row['source_table'], row['target_table'])
            for row in self.execute(query, *params)
        ]

    def mark_migrated(self, tables):
        with self.db:
            for table in tables:
                self.db.execute('update tables set migrated = 1 where source_table = ?', [table])

    def __enter__(self):
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()


class TableMigration(object):
    def __init__(self, table, command):
        self.table = table
        self.command = command
        self.process = None

    def run(self):
        print(self.command)
        self.process = subprocess.Popen(self.command, shell=True)
        return self

    def poll(self):
        return self.process.poll()

    def wait(self):
        return self.process.wait()

    def __repr__(self):
        return 'TableMigration({})'.format(self.table)


class MigrationPool(object):
    def __init__(self, max_size):
        self.max_size = max_size
        self._pool = set()
        self.errors = []

    def run(self, process):
        if self.errors:
            return

        complete = self.wait_for_capacity()
        self._pool.add(process.run())
        return complete

    def wait_for_capacity(self):
        if len(self._pool) < self.max_size:
            return

        complete = []
        while not complete:
            sleep(0.5)
            for process in frozenset(self._pool):
                code = process.poll()
                if code is not None:
                    self._pool.remove(process)
                    complete.append(process)
                    if code != 0:
                        self.errors.append(process)
        return complete

    def wait(self):
        complete = []
        for process in frozenset(self._pool):
            code = process.poll()
            if code is not None:
                if code > 0:
                    self.errors.append(process)
                else:
                    complete.append(process)
            else:
                process.wait()
        return complete


class Migrator(object):
    def __init__(self, db_path, source_db, source_host, source_user,
                 target_db, target_host, target_user,
                 start_date, end_date,
                 start_table, only_table, confirm, dry_run):
        self.db_path = db_path
        self.source_db = source_db
        self.source_host = source_host
        self.source_user = source_user
        self.target_db = target_db
        self.target_host = target_host
        self.target_user = target_user
        self.start_date = start_date
        self.end_date = end_date
        self.start_table = start_table
        self.only_table = only_table
        self.confirm = confirm
        self.dry_run = dry_run

        self.db = Database(self.db_path)

    def run(self):
        with self.db:
            if self.only_table:
                table = self.db.get_table(self.only_table)
                tables = [table]
            else:
                tables = self.db.get_tables(self.start_date, self.end_date)

            if not tables:
                raise Exception("No table to migrate")

            if self.dry_run or _confirm('Preparing to migrate {} tables.'.format(len(tables))):
                self.migrate_tables(tables)

    def migrate_tables(self, tables):
        table_sizes = None
        total_size = None
        progress = float(0)

        if not self.dry_run:
            table_sizes = get_table_sizes(self.source_db, self.source_host, self.source_user)

            if table_sizes is not None:
                source_tables = {source_table for source_table, target_table in tables}
                total_size = sum([size for table, size in table_sizes.items() if table in source_tables])

        def _update_progress(tables, progress):
            if table_sizes:
                for table in tables:
                    progress += table_sizes[table]
                print('\nProgress: {:.1f}% data ({} of {}), {:.1f}% tables ({} of {})\n'.format(
                    (100 * progress / total_size) if total_size else 100, int(progress), total_size,
                    100 * float(table_index) / total_tables, table_index, total_tables,
                ))
            return progress

        commands = self.get_dump_load_commands(tables)

        total_tables = len(tables)
        pool = MigrationPool(5)
        for table_index, [source_table, target_table, cmd] in enumerate(commands):
            if not self.dry_run and (not self.confirm or _confirm('Migrate {} to {}'.format(source_table, target_table))):
                complete = pool.run(TableMigration(source_table, cmd))
                if complete:
                    complete_tables = [m.table for m in complete if m not in pool.errors]
                    self.db.mark_migrated(complete_tables)
                    progress = _update_progress(complete_tables, progress)
            else:
                print(cmd)

        complete = pool.wait()
        self.db.mark_migrated([m.table for m in complete])

        if pool.errors:
            print("\nErrors encountered:")
            for process in pool.errors:
                print("\t{}".format(process.table))
            sys.exit(1)

    def get_dump_load_commands(self, tables):
        for source_table, target_table in tables:
            cmd = 'pg_dump -h {} -U {} -t {} {} --data-only --no-acl'.format(
                self.source_host, self.source_user, source_table, self.source_db
            )
            if target_table:
                cmd += ' | sed "s/\\"\\?{}\\"\\?/\\"{}\\"/g"'.format(source_table, target_table)
            cmd += ' | psql -h {} -U {} -v ON_ERROR_STOP=1 {} --single-transaction'.format(
                self.target_host, self.target_user, self.target_db
            )

            yield source_table, target_table, cmd


def get_table_sizes(source_db, source_host, source_user):
    try:
        from sqlalchemy import create_engine
    except ImportError:
        print('sqlalchemy not installed. Progress not supported.')
        return

    engine = create_engine("postgresql://{}:@{}/{}".format(source_user, source_host, source_db))
    with engine.begin() as conn:
        res = conn.execute("select relname, n_live_tup from pg_stat_user_tables")
        return {
            row.relname: row.n_live_tup
            for row in res
        }


def filter_tables_by_date(tables, start_date, end_date):
    return [
        (source_table, target_table) for source_table, table_date, target_table in tables
        if (not start_date or table_date >= start_date) and (not end_date or table_date < end_date)
    ]


def _confirm(msg):
    confirm_update = input(msg + ' [yes / no] ')
    return confirm_update == 'yes'


def main():
    parser = argparse.ArgumentParser(description="""
        Migrate DB tables from one DB to another using pg_dump.
        Compainion to custom/icds_reports/management_commands/generate_migration_tables.py
    """)
    parser.add_argument(
        'db_path',
        help='Path to sqlite DB containing list of tables to migrate'
    )
    parser.add_argument(
        '-D', '--source-db',
        required=True,
        help='Name for source database'
    )
    parser.add_argument(
        '-O', '--source-host',
        required=True,
        help='Name for source database'
    )
    parser.add_argument(
        '-U', '--source-user',
        required=True,
        help='Name for source database'
    )
    parser.add_argument(
        '-d', '--target-db',
        required=True,
        help='Name for target database'
    )
    parser.add_argument(
        '-o', '--target-host',
        required=True,
        help='Name for target database'
    )
    parser.add_argument(
        '-u', '--target-user',
        required=True,
        help='PG user to connect to target DB as. This user should be able to connect to the target'
             'DB without a password.',
    )
    parser.add_argument(
        '--start-date',
        type=parse_date,
        help='Only migrate tables with date on or after this date. Format YYYY-MM-DD',
    )
    parser.add_argument(
        '--end-date',
        type=parse_date,
        help='Only migrate tables with date before this date. Format YYYY-MM-DD',
    )
    parser.add_argument(
        '--start-after-table',
        help='Skip all tables up to and including this one',
    )
    parser.add_argument(
        '--table',
        help='Only migrate this table',
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Confirm before each table.',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only output the commands.',
    )

    args = parser.parse_args()

    migrator = Migrator(
        args.db_path, args.source_db, args.source_host, args.source_user,
        args.target_db, args.target_host, args.target_user,
        args.start_date, args.end_date,
        args.start_after_table, args.table, args.confirm, args.dry_run
    )
    migrator.run()


if __name__ == "__main__":
    main()
