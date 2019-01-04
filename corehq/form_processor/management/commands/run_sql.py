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
            help="Do not print returned rows. Has no effect on RunUntilZero "
                 "statements since results are not printed for those.")
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


@attr.s
class RunUntilZero(object):
    """SQL statement to be run repeatedly

    ...until the first column of the first returned row is zero.
    """

    sql = attr.ib()

    def format(self, **kw):
        return self.sql.format(**kw)

    @classmethod
    def run(cls, sql, dbname, print_rows):
        next_update = prev_update = datetime.now()
        next_processed = 0
        total = 0
        with timer(dbname), connections[dbname].cursor() as cursor:
            while True:
                try:
                    cursor.execute(sql)
                except Exception as err:
                    cls.handle_err(err, dbname)
                    continue
                rows = cursor.fetchmany(2)
                assert len(rows) == 1 and len(rows[0]) == 1, \
                    "expected 1 row with 1 column, got %r" % (rows,)
                moved = rows[0][0]
                if not moved:
                    break
                total += moved
                next_processed += moved
                now = datetime.now()
                if now > next_update:
                    secs = (now - prev_update).total_seconds() or 1
                    rate = int(next_processed / float(secs) + 0.5)
                    print("{}: processed {} items ({:.0f}/s)".format(
                        dbname, total, rate))
                    prev_update = now
                    next_update = now + timedelta(seconds=5)
                    next_processed = 0
        print("{} final: processed {} items".format(dbname, total))

    @classmethod
    def handle_err(cls, err, dbname):
        raise


import re  # noqa: E402
from collections import defaultdict  # noqa: E402
from django.db import IntegrityError, transaction  # noqa: E402
from corehq.blobs import CODES, get_blob_db  # noqa: E402
from corehq.blobs.models import BlobMeta  # noqa: E402

KEYRE = re.compile(r"DETAIL:  Key \(key\)=\((.*)\) already exists\.")


class RunUntilZeroHandleDupBlobs(RunUntilZero):
    # this will not be efficient if there are many duplicates

    @classmethod
    def handle_err(cls, err, dbname):
        if not isinstance(err, IntegrityError):
            raise
        match = KEYRE.search(six.text_type(err))
        if not match:
            raise
        key = match.group(1)
        key_metas = list(BlobMeta.objects.using(dbname).filter(key=key))
        by_parent = defaultdict(list)
        for meta in key_metas:
            by_parent[meta.parent_id].append(meta)
        diff_parents = []
        for metas in by_parent.values():
            if len(metas) == 1:
                diff_parents.append(metas[0])
                continue
            # handle form with duplicate attachments (old and new metadata)
            assert len(metas) == 2, metas
            f1, f2 = [cls.meta_fields(m, False) for m in metas]
            assert f1 == f2, "refusing to delete: {} != {}".format(f1, f2)
            m1, m2 = metas
            if m1.type_code != m2.type_code:
                # delete (new) metadata with bad type code. this happened as a
                # result of the earlier migration of relatively new SQL domains
                # that had thier defunct couch metadata migrated into the
                # blobmeta table, but with wrong type code
                real_type_code = (CODES.form_xml
                    if m1.name == "form.xml" else CODES.form_attachment)
                assert real_type_code in [m1.type_code, m2.type_code], \
                    (real_type_code, m1.type_code, m2.type_code)

                def sort_key(meta):
                    return 0 if meta.type_code == real_type_code else 1
            else:
                # delete the newer metadata
                def sort_key(meta):
                    return meta.created_on
            # sort_key should sort the one to keep before the one to delete
            metas.sort(key=sort_key)
            meta = metas.pop()
            print("{dbname}: deleting duplicate blob for "
                "{meta.parent_id} / {meta.name} key={key}".format(**locals()))
            meta.delete()
            diff_parents.append(metas[0])
        if len(diff_parents) > 1:
            # copy blob for all except one
            for meta in sorted(diff_parents, key=lambda m: m.id)[:-1]:
                print("{dbname}: creating new blob for {meta.parent_id} / "
                      "{meta.name} key={key}".format(**locals()))
                with meta.open() as content, transaction.atomic(using=dbname):
                    newmeta = get_blob_db().put(content, **cls.meta_fields(meta))
                    meta.delete()

    @staticmethod
    def meta_fields(meta, with_variable_fields=True):
        fields = {f: getattr(meta, f) for f in [
            "domain",
            "parent_id",
            "name",
            "content_length",
            "content_type",
            "properties",
            "expires_on",
        ]}
        if with_variable_fields:
            fields["type_code"] = meta.type_code
            fields["created_on"] = meta.created_on
        return fields


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


# see https://github.com/dimagi/commcare-hq/pull/21631
blobmeta_key = """
CREATE INDEX CONCURRENTLY IF NOT EXISTS form_processor_xformattachmentsql_blobmeta_key
ON public.form_processor_xformattachmentsql (((
    CASE
        WHEN blob_bucket = '' THEN '' -- empty bucket -> blob_id is the key
        ELSE COALESCE(blob_bucket, 'form/' || REPLACE(attachment_id::text, '-', '')) || '/'
    END || blob_id
)::varchar(255)))
"""


TEMPLATES = {
    "blobmeta_key": blobmeta_key,
    "show_invalid_indexes": show_invalid_indexes,

    # use to verify tables are empty
    # warning, may be slow (requires a table scan) if the table has many records
    "count_form_attachments":
        "SELECT COUNT(*) FROM form_processor_xformattachmentsql;"
}
