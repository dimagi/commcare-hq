from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import sys
import traceback

import gevent
from django.core.management.base import BaseCommand
from django.db import connections
from six.moves import input

from corehq.sql_db.util import get_db_aliases_for_partitioned_query

MULTI_DB = 'Executing on ALL (%s) databases in parallel. Continue?'


class Command(BaseCommand):
    help = """Run SQL concurrently on partition databases."""

    def add_arguments(self, parser):
        parser.add_argument('name', choices=list(STATEMENTS), help="SQL statement name.")
        parser.add_argument('-d', '--dbname', help='Django DB alias to run on')

    def handle(self, name, dbname, **options):
        sql = STATEMENTS[name]
        dbnames = get_db_aliases_for_partitioned_query()
        if dbname or len(dbnames) == 1:
            run_sql(dbname or dbnames[0], sql)
        elif not confirm(MULTI_DB % len(dbnames)):
            sys.exit('abort')
        else:
            greenlets = []
            for dbname in dbnames:
                g = gevent.spawn(run_sql, dbname, sql)
                greenlets.append(g)

            gevent.joinall(greenlets)
            try:
                for job in greenlets:
                    job.get()
            except Exception:
                traceback.print_exc()


def confirm(msg):
    return input(msg + "\n(y/N) ").lower() == 'y'


def run_sql(dbname, sql):
    print("running on %s database" % dbname)
    with connections[dbname].cursor() as cursor:
        cursor.execute(sql)


# see https://github.com/dimagi/commcare-hq/pull/21631
BLOBMETA_KEY_SQL = """
CREATE INDEX CONCURRENTLY IF NOT EXISTS form_processor_xformattachmentsql_blobmeta_key
ON public.form_processor_xformattachmentsql (((
    CASE
        WHEN blob_bucket = '' THEN '' -- empty bucket -> blob_id is the key
        ELSE COALESCE(blob_bucket, 'form/' || attachment_id) || '/'
    END || blob_id
)::varchar(255)))
"""


STATEMENTS = {
    "blobmeta_key": BLOBMETA_KEY_SQL,
}
