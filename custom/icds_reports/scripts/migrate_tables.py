from __future__ import absolute_import, print_function
from __future__ import unicode_literals, division

import argparse
import json
import logging
import sqlite3
import subprocess
import sys
from datetime import datetime
from time import sleep

from six.moves import input
from io import open

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
    def __init__(self, db_path, retry_errors=False):
        self.db_path = db_path
        self.retry_errors = retry_errors

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
        filters, params = self._get_date_filters_params(start_date, end_date)

        query = 'SELECT * FROM tables WHERE migrated is null'
        if not self.retry_errors:
            query += '  and errored is null'

        if filters:
            query += ' and ({})'.format(' and '.join(filters))
        return [
            (row['source_table'], row['target_table'])
            for row in self.execute(query, *params)
        ]

    def _get_date_filters_params(self, start_date, end_date):
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
        return filters, params

    def mark_migrated(self, table, success):
        with self.db:
            field = 'migrated' if success else 'errored'
            self.db.execute('update tables set {} = 1 where source_table = ?'.format(field), [table])

    def __enter__(self):
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()


class CommandWithContext(object):
    def __init__(self, command, context, callback=None):
        self.context = context
        self.command = command
        self.process = None
        self.callback = callback

    def run(self):
        self.process = subprocess.Popen(self.command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return self

    def poll(self):
        ret = self.process.poll()
        if ret is not None:
            self.call_callback(ret)
        return ret

    def wait(self):
        ret = self.process.wait()
        self.call_callback(ret)
        return ret

    def call_callback(self, ret_code):
        if self.callback:
            stdout = self.process.stdout.read()
            stderr = self.process.stderr.read()
            self.callback(self.context, ret_code, stdout, stderr)

    def __repr__(self):
        return 'CommandWithContext({})'.format(self.context)


class MigrationPool(object):
    def __init__(self, max_size, callback, stop_on_error=True):
        self.max_size = max_size
        self._pool = set()
        self.has_errors = False
        self.callback = callback
        self.stop_on_error = stop_on_error

    def run(self, command, context):
        if self.has_errors and self.stop_on_error:
            return

        self.wait_for_capacity()

        process = CommandWithContext(command, context, self.callback)
        self._pool.add(process.run())

    def wait_for_capacity(self):
        while len(self._pool) >= self.max_size:
            sleep(0.5)
            for process in frozenset(self._pool):
                code = process.poll()
                if code is not None:
                    self._pool.remove(process)
                    self.has_errors |= code != 0

    def wait(self):
        for process in frozenset(self._pool):
            code = process.poll()
            if code is None:
                process.wait()


class Migrator(object):
    def __init__(self, db_path, source_db, source_host, source_user,
                 target_db, target_host, target_user,
                 start_date, end_date,
                 only_table, confirm, dry_run,
                 stop_on_error, retry_errors):
        self.db_path = db_path
        self.source_db = source_db
        self.source_host = source_host
        self.source_user = source_user
        self.target_db = target_db
        self.target_host = target_host
        self.target_user = target_user
        self.start_date = start_date
        self.end_date = end_date
        self.only_table = only_table
        self.confirm = confirm
        self.dry_run = dry_run
        self.stop_on_error = stop_on_error

        self.error_log = 'icds_citus_migration_errors-{}.log'.format(datetime.utcnow().isoformat())

        self.db = Database(self.db_path, retry_errors)

    def run(self, max_concurrent):

        print('\n\nWriting error logs to {}\n\n'.format(self.error_log))

        with self.db:
            if self.only_table:
                table = self.db.get_table(self.only_table)
                tables = [table]
            else:
                tables = self.db.get_tables(self.start_date, self.end_date)

            if not tables:
                raise Exception("No table to migrate")

            if self.dry_run or _confirm('Preparing to migrate {} tables.'.format(len(tables))):
                self.migrate_tables(tables, max_concurrent)

    def write_error(self, context, ret_code, stdout, stderr):
        stderr = stderr.decode()
        error, detail, context_line = None, None, None
        try:
            lines = stderr.splitlines()
            if len(lines) == 2:
                error, detail = lines
            elif len(lines) == 3:
                error, detail, context_line = lines

            error = error.split(':  ')[1] if error else None
            detail = detail.split(':  ')[1] if detail else None
            context_line = context_line.split(':  ')[1] if context_line else None
        except Exception:
            pass

        error_json = context.copy()
        error_json.update({
            'ret_code': ret_code,
            'stdout': stdout.decode(),
            'stderr': stderr,
            'ERROR': error,
            'DETAIL': detail,
            'CONTEXT': context_line
        })
        with open(self.error_log, 'a') as out:
            out.write('{}\n'.format(json.dumps(error_json)))

    def migrate_tables(self, tables, max_concurrent):
        table_sizes = None
        total_size = None
        progress = []
        error_progress = []
        completed = []
        errors = []
        total_tables = len(tables)
        start_time = datetime.now()

        if not self.dry_run:
            table_sizes = get_table_sizes(self.source_db, self.source_host, self.source_user)

            if table_sizes is not None:
                source_tables = {source_table for source_table, target_table in tables}
                total_size = sum([size for table, size in table_sizes.items() if table in source_tables])

        def _update_progress(context, ret_code, stdout, stderr):
            success = ret_code == 0
            completed.append(context['source_table'])
            if not success:
                errors.append(context['source_table'])
            self.db.mark_migrated(context['source_table'], success)
            print('{} {}'.format('[ERROR] ' if not success else '', context['cmd']))
            if stdout:
                print(stdout.decode())
            if stderr:
                print(stderr.decode())
            if not success:
                self.write_error(context, ret_code, stdout, stderr)

            table_progress = len(completed) + 1
            table_errors = len(errors)
            elapsed = datetime.now() - start_time
            if table_sizes:
                progress.append(context['size'])
                if not success:
                    error_progress.append(context['size'])
                data_progress = sum(progress)
                data_errors = sum(error_progress)
                remaining = elapsed // data_progress * total_size if data_progress else 'unknown'
                print(
                    '\nProgress: '
                    '{data_percent:.1f}% data ({data_progress} of {data_total}) ({data_errors} errored), '
                    '{tables_percent:.1f}% tables ({tables_progress} of {tables_total}) ({table_errors} errored) '
                    'in {elapsed} ({remaining} remaining)\n'.format(
                        data_percent=(100 * float(data_progress) / total_size) if total_size else 100,
                        data_progress=data_progress,
                        data_total=total_size,
                        data_errors=data_errors,
                        tables_percent=100 * float(table_progress) / total_tables,
                        tables_progress=table_progress,
                        tables_total=total_tables,
                        table_errors=table_errors,
                        elapsed=elapsed,
                        remaining=remaining
                    )
                )
            else:
                print(
                    '\nProgress: '
                    '{tables_percent:.1f}% tables ({tables_progress} of {tables_total}) ({table_errors} errored) '
                    'in {elapsed}\n'.format(
                        tables_percent=100 * float(table_progress) / total_tables,
                        tables_progress=table_progress,
                        tables_total=total_tables,
                        table_errors=table_errors,
                        elapsed=elapsed,
                    )
                )

        commands = self.get_dump_load_commands(tables)

        pool = MigrationPool(max_concurrent, _update_progress, stop_on_error=self.stop_on_error)
        for table_index, [source_table, target_table, cmd] in enumerate(commands):
            confirm_msg = 'Migrate {} to {}'.format(source_table, target_table)
            if not self.dry_run and (not self.confirm or _confirm(confirm_msg)):
                pool.run(cmd, {
                    'cmd': cmd,
                    'source_table': source_table,
                    'target_table': target_table,
                    'size': table_sizes[source_table] if table_sizes else 0
                })
            else:
                print(cmd)

        pool.wait()

        if pool.has_errors:
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
        print('\nsqlalchemy not installed. Progress not supported.\n')
        return

    engine = create_engine("postgresql://{}:@{}/{}".format(source_user, source_host, source_db))
    with engine.begin() as conn:
        res = conn.execute("select relname, n_live_tup from pg_stat_user_tables")
        return {
            row.relname: row.n_live_tup
            for row in res
        }


def _confirm(msg):
    confirm_update = input(msg + ' [yes / no] ')
    return confirm_update == 'yes'


def stats(db_path, **kwargs):
    db = Database(db_path)
    with db:
        res = db.execute('select migrated, errored, count(*) as count from tables group by migrated, errored')
    migrated, errored, total = 0, 0, 0
    for row in res:
        total += row['count']
        if row['migrated']:
            migrated += row['count']
        if row['errored']:
            errored += row['count']
    print("""
    Migration stats:
        Total   : {}
        Migrated: {} ({}%)
        Errored : {} ({}%)
    """.format(total, migrated, 100 * migrated // total, errored, 100 * errored // total))


def print_table(rows):
    cols = [
        ('source_table', '<', 55),
        ('date', '<', 15),
        ('migrated', '^', 8),
        ('errored', '^', 8),
        ('target_table', '<', 50)
    ]
    template = " | ".join(['{{{}:{}{}}}'.format(*col) for col in cols])
    print(template.format(
        source_table='Source Table',
        date='Table Date',
        migrated='Migrated',
        errored='Errored',
        target_table='Target Table'
    ))
    for row in rows:
        row = {
            col: val if val is not None else ''
            for col, val in dict(row).items()
        }
        print(template.format(**row))


def list_tables(db_path, start_date, end_date, migrated=False, errored=False):
    db = Database(db_path)

    query = 'select * from tables'

    filters, params = db._get_date_filters_params(start_date, end_date)
    if migrated:
        filters.append('migrated = 1')
    if errored:
        filters.append('errored = 1')
    if filters:
        query += ' where {}'.format(' and '.join(filters))

    with db:
        res = db.execute(query, *params)

    print_table(res)


def main():
    parser = argparse.ArgumentParser(description="""
        Migrate DB tables from one DB to another using pg_dump.
        Compainion to custom/icds_reports/management_commands/generate_migration_tables.py
    """)
    subparser = parser.add_subparsers(dest='action')

    status_parser = subparser.add_parser('status')
    status_parser.add_argument('db_path', help='Path to sqlite DB containing list of tables to migrate')
    status_parser.add_argument(
        'command',
        nargs='?',
        choices=('stats', 'list'),
        default='stats',
    )
    status_parser.add_argument('-s', '--start-date', type=parse_date, help=(
        'Only show tables with date on or after this date. Format YYYY-MM-DD. Only applies to "list".'
    ))
    status_parser.add_argument('-e', '--end-date', type=parse_date, help=(
        'Only show tables with date before this date. Format YYYY-MM-DD. Only applies to "list".'
    ))
    status_parser.add_argument('-M', '--migrated', action='store_true', help=(
        'Only show migrated tables. Only applies to "list".'
    ))
    status_parser.add_argument('-E', '--errored', action='store_true', help=(
        'Only show errored tables. Only applies to "list".'
    ))

    migrate_parser = subparser.add_parser('migrate')
    migrate_parser.add_argument('db_path', help='Path to sqlite DB containing list of tables to migrate')
    migrate_parser.add_argument('-D', '--source-db', required=True, help='Name for source database')
    migrate_parser.add_argument('-O', '--source-host', required=True, help='Name for source database')
    migrate_parser.add_argument('-U', '--source-user', required=True, help='Name for source database')
    migrate_parser.add_argument('-d', '--target-db', required=True, help='Name for target database')
    migrate_parser.add_argument('-o', '--target-host', required=True, help='Name for target database')
    migrate_parser.add_argument('-u', '--target-user', required=True, help=(
        'PG user to connect to target DB as. This user should be able to connect to the target'
        'DB without a password.'
    ))
    migrate_parser.add_argument('--start-date', type=parse_date, help=(
        'Only migrate tables with date on or after this date. Format YYYY-MM-DD'
    ))
    migrate_parser.add_argument('--end-date', type=parse_date, help=(
        'Only migrate tables with date before this date. Format YYYY-MM-DD'
    ))
    migrate_parser.add_argument('--table', help='Only migrate this table')
    migrate_parser.add_argument('--confirm', action='store_true', help='Confirm before each table.')
    migrate_parser.add_argument('--dry-run', action='store_true', help='Only output the commands.')
    migrate_parser.add_argument('--parallel', type=int, default=1, help='How many commands to run in parallel')
    migrate_parser.add_argument('--no-stop-on-error', action='store_true', help=(
        'Do not stop the migration if an error is encountered'
    ))
    migrate_parser.add_argument('--retry-errors', action='store_true', help='Retry tables that have errored')

    args = parser.parse_args()

    if args.action == 'migrate':
        migrator = Migrator(
            args.db_path, args.source_db, args.source_host, args.source_user,
            args.target_db, args.target_host, args.target_user,
            args.start_date, args.end_date,
            args.table, args.confirm, args.dry_run,
            not args.no_stop_on_error, args.retry_errors
        )
        migrator.run(args.parallel)
    elif args.action == 'status':
        kwargs = vars(args)
        kwargs.pop('action')
        command = kwargs.pop('command')
        {
            'stats': stats,
            'list': list_tables
        }[command](**kwargs)


if __name__ == "__main__":
    main()
