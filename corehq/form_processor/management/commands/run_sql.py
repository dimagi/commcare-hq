from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import sys
import traceback

import attr
import gevent
from django.core.management.base import BaseCommand
from django.db import connections
from six.moves import input

from corehq.sql_db.util import get_db_aliases_for_partitioned_query


@attr.s
class Statement(object):
    sql = attr.ib()
    help = attr.ib(default="")


BLOBMETA_KEY = Statement("""
CREATE INDEX CONCURRENTLY IF NOT EXISTS form_processor_xformattachmentsql_blobmeta_key
ON public.form_processor_xformattachmentsql (((
    CASE
        WHEN blob_bucket = '' THEN '' -- empty bucket -> blob_id is the key
        ELSE COALESCE(blob_bucket, 'form/' || attachment_id) || '/'
    END || blob_id
)::varchar(255)))
""", help="See https://github.com/dimagi/commcare-hq/pull/21631")

STATEMENTS = {
    "blobmeta_key": BLOBMETA_KEY,
}

MULTI_DB = 'Execute on ALL (%s) databases in parallel. Continue?'


class Command(BaseCommand):
    help = """Run SQL concurrently on partition databases."""

    def add_arguments(self, parser):
        parser.add_argument('name', choices=list(STATEMENTS), help="SQL statement name.")
        parser.add_argument('-d', '--db_name', help='Django DB alias to run on')

    def handle(self, name, db_name, **options):
        sql = STATEMENTS[name].sql
        db_names = get_db_aliases_for_partitioned_query()
        if db_name or len(db_names) == 1:
            run_sql(db_name or db_names[0], sql)
        elif not confirm(MULTI_DB % len(db_names)):
            sys.exit('abort')
        else:
            greenlets = []
            for db_name in db_names:
                g = gevent.spawn(run_sql, db_name, sql)
                greenlets.append(g)

            gevent.joinall(greenlets)
            try:
                for job in greenlets:
                    job.get()
            except Exception:
                traceback.print_exc()


def run_sql(db_name, sql):
    print("running on %s database" % db_name)
    with connections[db_name].cursor() as cursor:
        cursor.execute(sql)


def confirm(msg):
    return input(msg + "\n(y/N) ").lower() == 'y'
