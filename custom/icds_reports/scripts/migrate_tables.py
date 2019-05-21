from __future__ import absolute_import, print_function
from __future__ import unicode_literals

import argparse
import inspect
import logging
import subprocess
import sys
from datetime import datetime, date

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


def run_migration(
    table_path, source_db, source_host, source_user,
    target_db, target_host, target_user,
    start_date, end_date,
    start_table, only_table, confirm, dry_run
):
    tables = []
    with open(table_path, 'r') as file:
        for line in file.readlines():
            source_table, date_str, target_table = line.strip().split(',')
            tables.append((source_table, parse_date(date_str, date.max), target_table))

    filtered_tables = filter_tables_by_date(tables, start_date, end_date)
    if start_table:
        start_index = [i for i, t in enumerate(filtered_tables) if t[0] == start_table]
        if not start_index:
            raise Exception('start table not found')
        else:
            start_index = start_index[0] + 1
            filtered_tables = filtered_tables[start_index:]

    if only_table:
        filtered_tables = [
            table for table in filtered_tables if table[0] == only_table
        ]
    if not filtered_tables:
        raise Exception("No table to migrate")

    if dry_run or _confirm('Preparing to migrate {} tables.'.format(len(filtered_tables))):
        migrate_tables(
            filtered_tables, source_db, source_host, source_user,
            target_db, target_host, target_user,
            confirm, dry_run
        )


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


def migrate_tables(tables, source_db, source_host, source_user, target_db, target_host, target_user, confirm, dry_run):
    table_sizes = get_table_sizes(source_db, source_host, source_user)

    total_size = None
    progress = float(0)
    if table_sizes is not None:
        source_tables = {source_table for source_table, target_table in tables}
        total_size = sum([size for table, size in table_sizes.items() if table in source_tables])

    commands = get_dump_load_commands(
        tables, source_db, source_host, source_user, target_db, target_host, target_user
    )

    total_tables = len(tables)
    for table_index, [source_table, target_table, cmd] in enumerate(commands):
        print(cmd)
        if not dry_run and (not confirm or _confirm('Migrate {} to {}'.format(source_table, target_table))):
            code = subprocess.call(cmd, shell=True)
            if code != 0:
                sys.exit(code)
        if table_sizes:
            progress += table_sizes[source_table]
            print('\nProgress: {:.1f}% data ({} of {}), {:.1f}% tables ({} of {})\n'.format(
                100 * progress / total_size, int(progress), total_size,
                100 * float(table_index) / total_tables, table_index, total_tables,
            ))


def filter_tables_by_date(tables, start_date, end_date):
    return [
        (source_table, target_table) for source_table, table_date, target_table in tables
        if (not start_date or table_date >= start_date) and (not end_date or table_date < end_date)
    ]


def get_dump_load_commands(tables, source_db, source_host, source_user, target_db, target_host, target_user):
    for source_table, target_table in tables:
        cmd = 'pg_dump -h {} -U {} -t {} {} --data-only --no-acl'.format(
            source_host, source_user, source_table, source_db
        )
        if target_table:
            cmd += ' | sed "s/{}/{}/g"'.format(source_table, target_table)
        cmd += ' | psql -h {} -U {} -v ON_ERROR_STOP=1 {} --single-transaction'.format(
            target_host, target_user, target_db
        )

        yield source_table, target_table, cmd


def _confirm(msg):
    confirm_update = input(msg + ' [yes / no] ')
    return confirm_update == 'yes'


def main():
    parser = argparse.ArgumentParser(description="Migrate DB tables from one DB to another using pg_dump")
    parser.add_argument(
        'table_path',
        help=inspect.cleandoc("""
        Path to list file containing list of tables formatted as CSV.
        File should have 3 columns in this order: source_table_name,table_date,target_table_name
            source_table_name: name of table in source DB
            table_date: For tables partitioned by month this should be the month of the data
                        in the table e.g. 2018-03-01
            target_table_name: name of the table to load the data into in the target database
        """)
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

    run_migration(
        args.table_path, args.source_db, args.source_host, args.source_user,
        args.target_db, args.target_host, args.target_user,
        args.start_date, args.end_date,
        args.start_after_table, args.table, args.confirm, args.dry_run
    )


if __name__ == "__main__":
    main()
