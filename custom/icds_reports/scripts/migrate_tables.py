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
    table_path, source_db,
    target_db, target_host, target_user,
    start_date, end_date,
    only_table, confirm, dry_run
):
    tables = []
    with open(table_path, 'r') as file:
        for line in file.readlines():
            source_table, date_str, target_table = line.strip().split(',')
            tables.append((source_table, parse_date(date_str, date.max), target_table))

    filtered_tables = filter_tables_by_date(tables, start_date, end_date)
    if only_table:
        filtered_tables = [
            table for table in filtered_tables if table[0] == only_table
        ]
    if not filtered_tables:
        raise Exception("No table to migrate")

    if dry_run or _confirm('Preparing to migrate {} tables.'.format(len(filtered_tables))):
        migrate_tables(
            filtered_tables, source_db, target_db,
            target_host, target_user, confirm, dry_run
        )


def migrate_tables(tables, source_db, target_db, target_host, target_user, confirm, dry_run):
    commands = get_dump_load_commands(tables, source_db, target_db, target_host, target_user)
    for source_table, target_table, cmd_parts in commands:
        cmd = ' '.join(cmd_parts)
        print(cmd)
        if not dry_run and (not confirm or _confirm('Migrate {} to {}'.format(source_table, target_table))):
            code = subprocess.call(cmd, shell=True)
            if code != 0:
                sys.exit(code)


def filter_tables_by_date(tables, start_date, end_date):
    return [
        (source_table, target_table) for source_table, table_date, target_table in tables
        if (not start_date or table_date >= start_date) and (not end_date or table_date < end_date)
    ]


def get_dump_load_commands(tables, source_db, target_db, target_host, target_user):
    dump_opts = ['--data-only', '--no-acl']
    load_opts = ['-h', target_host, '-U', target_user, target_db]
    for source_table, target_table in tables:
        cmd_parts = ['pg_dump', '-t', source_table, source_db] + dump_opts
        if target_table:
            cmd_parts += ['|', 'sed', '"s/{}/{}/g"'.format(source_table, target_table)]
        cmd_parts += ['|', 'psql'] + load_opts
        yield source_table, target_table, cmd_parts


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
        '-d', '--source-db',
        required=True,
        help='Name for source database'
    )
    parser.add_argument(
        '-t', '--target-db',
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
        args.table_path, args.source_db,
        args.target_db, args.target_host, args.target_user,
        args.start_date, args.end_date,
        args.table, args.confirm, args.dry_run
    )


if __name__ == "__main__":
    main()
