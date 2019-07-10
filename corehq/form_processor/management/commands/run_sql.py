"""Run SQL concurrently on partition databases

SQL statement templates may use the `{chunk_size}` placeholder, which
will be replaced with the value of the --chunk-size=N command argument.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import pprint
import sys
import traceback
from datetime import datetime, timedelta
from contextlib import contextmanager

import attr
import gevent
import six
from django.core.management.base import BaseCommand
from django.db import connections
from six.moves import input

from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.teeout import tee_output
from six.moves import zip

MULTI_DB = 'Executing on ALL (%s) databases in parallel. Continue?'


class Command(BaseCommand):
    help = """Run SQL concurrently on partition databases."""

    def add_arguments(self, parser):
        parser.add_argument('name', choices=list(TEMPLATES), help="SQL statement name.")
        parser.add_argument('-d', '--dbname', help='Django DB alias to run on.')
        parser.add_argument('--chunk-size', type=int, default=1000,
            help="Maximum number of records to move at once.")
        parser.add_argument('-y', '--yes', action="store_true",
            help='Answer yes to run on all databases prompt.')
        parser.add_argument('--ignore-rows',
            action="store_false", dest="print_rows", default=True,
            help="Do not print returned rows.")
        parser.add_argument('-o', '--log-output', action="store_true",
            help='Log output to a file: ./NAME-TIMESTAMP.log')

    def handle(self, name, dbname, chunk_size, yes, print_rows, **options):
        template = TEMPLATES[name]
        sql = template.format(chunk_size=chunk_size)
        run = getattr(template, "run", run_once)
        dbnames = get_db_aliases_for_partitioned_query()
        if options.get('log_output'):
            logfile = "{}-{}.log".format(name, datetime.now().isoformat())
            print("writing output to file: {}".format(logfile))
        else:
            logfile = None
        with tee_output(logfile):
            if dbname or len(dbnames) == 1:
                run(sql, dbname or dbnames[0], print_rows)
            elif not (yes or confirm(MULTI_DB % len(dbnames))):
                sys.exit('abort')
            else:
                greenlets = []
                for dbname in dbnames:
                    g = gevent.spawn(run, sql, dbname, print_rows)
                    greenlets.append(g)

                gevent.joinall(greenlets)
                try:
                    for job in greenlets:
                        job.get()
                except Exception:
                    traceback.print_exc()


def confirm(msg):
    return input(msg + "\n(y/N) ").lower() == 'y'


@contextmanager
def timer(dbname):
    print("running on %s database" % dbname)
    start = datetime.now()
    try:
        yield
    finally:
        print("{} elapsed: {}".format(dbname, datetime.now() - start))


def fetch_dicts(cursor):
    try:
        rows = cursor.fetchall()
    except Exception as err:
        if six.text_type(err) != "no results to fetch":
            raise
        rows = []
    if not rows:
        return []
    cols = [col[0] for col in cursor.description]
    return [{c: v for c, v in zip(cols, row)} for row in rows]


def run_once(sql, dbname, print_rows):
    """Run sql statement once on database

    This is the default run mode for statements
    """
    with connections[dbname].cursor() as cursor, timer(dbname):
        cursor.execute(sql)
        if print_rows:
            rows = fetch_dicts(cursor)
            for row in rows:
                pprint.pprint(row)
            print("({} rows from {})".format(len(rows), dbname))


# Run after creating an index concurrently to verify successful index
# creation. Each printed row represents an invalid index.
# source https://stackoverflow.com/a/29260046/10840
show_invalid_indexes = """
SELECT n.nspname, c.relname
FROM   pg_catalog.pg_class c, pg_catalog.pg_namespace n,
       pg_catalog.pg_index i
WHERE  (i.indisvalid = false OR i.indisready = false) AND
       i.indexrelid = c.oid AND c.relnamespace = n.oid AND
       n.nspname != 'pg_catalog' AND
       n.nspname != 'information_schema' AND
       n.nspname != 'pg_toast'
"""


TEMPLATES = {
    "show_invalid_indexes": show_invalid_indexes,
}
