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


# Move rows incrementally.
# WARNING monitor disk usage when running in large environments.
# Does not require downtime, but may be slow.
# This version should work on icds, but not prod and probably not india.
simple_move_form_attachments_to_blobmeta = RunUntilZeroHandleDupBlobs("""
WITH deleted AS (
    DELETE FROM form_processor_xformattachmentsql
    WHERE id IN (
        SELECT id FROM form_processor_xformattachmentsql
        LIMIT {chunk_size}
    )
    RETURNING *
), moved AS (
    INSERT INTO blobs_blobmeta_tbl (
        "domain",
        parent_id,
        "name",
        "key",
        type_code,
        content_type,
        properties,
        created_on,
        content_length
    ) SELECT
        COALESCE(xform."domain", '<unknown>'),
        att.form_id AS parent_id,
        att."name",
        (CASE
            WHEN att.blob_bucket = '' THEN '' -- empty bucket -> blob_id is the key
            ELSE COALESCE(
                att.blob_bucket,
                'form/' || REPLACE(att.attachment_id::text, '-', '')
            ) || '/'
        END || att.blob_id)::VARCHAR(255) AS "key",
        CASE
            WHEN att."name" = 'form.xml' THEN 2 -- corehq.blobs.CODES.form_xml
            ELSE 3 -- corehq.blobs.CODES.form_attachment
        END::SMALLINT AS type_code,
        att.content_type,
        CASE
            WHEN att.properties = '{{}}' THEN NULL
            ELSE att.properties
        END AS properties,
        COALESCE(xform.received_on, CURRENT_TIMESTAMP) AS created_on,
        att.content_length
    FROM deleted att
    -- outer join so we move deleted rows with no corresponding xform instance
    -- should not happen, but just in case (without this they would be lost)
    LEFT OUTER JOIN form_processor_xforminstancesql xform
        ON xform.form_id = att.form_id
    RETURNING *
) SELECT COUNT(*) FROM moved
""")


# Move rows incrementally.
# WARNING monitor disk usage when running in large environments.
# Does not require downtime, but may be slow.
# This variant may be faster than the "simple" version above if there
# are many duplicate metadata records. However, it will likely "finish"
# before all records have been migrated due to returning zero even
# though there are more to migrate.
move_form_attachments_to_blobmeta = RunUntilZeroHandleDupBlobs("""
WITH to_move AS (
    SELECT
        COALESCE(xform."domain", '<unknown>') AS "domain",
        att.form_id AS parent_id,
        att."name",
        (CASE
            WHEN att.blob_bucket = '' THEN '' -- empty bucket -> blob_id is the key
            ELSE COALESCE(
                att.blob_bucket,
                'form/' || REPLACE(att.attachment_id::text, '-', '')
            ) || '/'
        END || att.blob_id)::VARCHAR(255) AS "key",
        CASE
            WHEN att."name" = 'form.xml' THEN 2 -- corehq.blobs.CODES.form_xml
            ELSE 3 -- corehq.blobs.CODES.form_attachment
        END::SMALLINT AS type_code,
        att.content_type,
        CASE
            WHEN att.properties = '{{}}' THEN NULL
            ELSE att.properties
        END AS properties,
        COALESCE(xform.received_on, CURRENT_TIMESTAMP) AS created_on,
        att.content_length
    FROM form_processor_xformattachmentsql att
    -- outer join so we move deleted rows with no corresponding xform instance
    -- should not happen, but just in case (without this they would be lost)
    LEFT OUTER JOIN form_processor_xforminstancesql xform
        ON xform.form_id = att.form_id
    LIMIT {chunk_size}
), moved AS (
    INSERT INTO blobs_blobmeta_tbl AS blob (
        "domain",
        parent_id,
        "name",
        "key",
        type_code,
        content_type,
        properties,
        created_on,
        content_length
    )
    SELECT * FROM to_move
    ON CONFLICT (key)
        DO UPDATE SET created_on = EXCLUDED.created_on
        -- this where clause will exclude a row with key conflict belonging to
        -- a different parent or with different name (unexpected, but possible)
        WHERE blob.parent_id = EXCLUDED.parent_id AND blob.name = EXCLUDED.name
    RETURNING *
), deleted AS (
    -- do the delete last so we only delete rows that were inserted or updated
    -- unfortunately this requires a bit more complex where clause because it
    -- is not possible to pass form_processor_xformattachmentsql.id through
    -- INSERT INTO blobs_blobmeta_tbl ... RETURNING
    DELETE FROM form_processor_xformattachmentsql att
    USING moved WHERE moved.parent_id = att.form_id
    AND moved.name = att.name
    AND moved.key = (CASE
        WHEN att.blob_bucket = '' THEN '' -- empty bucket -> blob_id is the key
        ELSE COALESCE(
            att.blob_bucket,
            'form/' || REPLACE(att.attachment_id::text, '-', '')
        ) || '/'
    END || att.blob_id)::VARCHAR(255)
    RETURNING *
) SELECT COUNT(*) FROM deleted;
""")


# this is too slow, so probably will not be used on envs like ICDS and prod
delete_dup_form_attachments = RunUntilZero("""
BEGIN;
WITH dups AS (
    SELECT * FROM (
        SELECT
            att.id,
            att.form_id,
            (CASE
                WHEN blob_bucket = '' THEN '' -- empty bucket -> blob_id is the key
                ELSE COALESCE(
                    blob_bucket,
                    'form/' || REPLACE(attachment_id::text, '-', '')
                ) || '/'
            END || blob_id) AS key
        FROM form_processor_xformattachmentsql att
    ) AS att
    WHERE EXISTS (
        SELECT 1 FROM blobs_blobmeta_tbl blob
        WHERE blob.key = att.key
        AND blob.parent_id = att.form_id
        AND blob.name = att.name
    )
    LIMIT {chunk_size}
), deleted AS (
    DELETE FROM form_processor_xformattachmentsql att
    USING dups WHERE att.id = dups.id
), updated AS (
    -- fix create_on date
    UPDATE blobs_blobmeta_tbl
    SET created_on = xform.received_on
    FROM dups
    INNER JOIN form_processor_xforminstancesql xform
        ON xform.form_id = dups.form_id
    WHERE blobs_blobmeta_tbl.key = dups.key
    RETURNING blobs_blobmeta_tbl.*
) SELECT COUNT(*) FROM updated;
""")


# move all rows in one go.
# requires table lock, so may not be feasible without some downtime.
# this may be necessary if MOVE_FORM_ATTACHMENTS is too slow.
blobmeta_forms = """
BEGIN;
LOCK TABLE blobs_blobmeta_tbl IN SHARE MODE;

-- drop indexes/constaints
ALTER TABLE blobs_blobmeta_tbl DROP CONSTRAINT blobs_blobmeta_pkey;
ALTER TABLE blobs_blobmeta_tbl DROP CONSTRAINT blobs_blobmeta_key_a9ed5760_uniq;
DROP INDEX blobs_blobm_expires_64b92d_partial;
DROP INDEX blobs_blobmeta_parent_id_type_code_name_9a2a0a9e_idx;
ALTER TABLE blobs_blobmeta_tbl DROP CONSTRAINT IF EXISTS blobs_blobmeta_type_code_check;
ALTER TABLE blobs_blobmeta_tbl DROP CONSTRAINT IF EXISTS blobs_blobmeta_content_length_check;

-- copy rows as quickly as possible
INSERT INTO blobs_blobmeta_tbl (
    "domain",
    parent_id,
    "name",
    "key",
    type_code,
    content_type,
    properties,
    created_on,
    content_length
) SELECT
    COALESCE(xform."domain", '<unknown>'),
    att.form_id AS parent_id,
    att."name",
    (CASE
        WHEN att.blob_bucket = '' THEN '' -- empty bucket -> blob_id is the key
        ELSE COALESCE(
            att.blob_bucket,
            'form/' || REPLACE(att.attachment_id::text, '-', '')
        ) || '/'
    END || att.blob_id)::VARCHAR(255) AS "key",
    CASE
        WHEN att."name" = 'form.xml' THEN 2 -- corehq.blobs.CODES.form_xml
        ELSE 3 -- corehq.blobs.CODES.form_attachment
    END::SMALLINT AS type_code,
    att.content_type,
    CASE
        WHEN att.properties = '{{}}' THEN NULL
        ELSE att.properties
    END AS properties,
    COALESCE(xform.received_on, CURRENT_TIMESTAMP) AS created_on,
    att.content_length
FROM form_processor_xformattachmentsql att
-- outer join so we move rows with no corresponding xform instance
-- should not happen, but just in case (without this they would be lost)
LEFT OUTER JOIN form_processor_xforminstancesql xform
    ON xform.form_id = att.form_id;

DELETE FROM form_processor_xformattachmentsql;

-- re-add indexes/constraints
ALTER TABLE blobs_blobmeta_tbl ADD CONSTRAINT blobs_blobmeta_pkey
    PRIMARY KEY (id);
ALTER TABLE blobs_blobmeta_tbl ADD CONSTRAINT blobs_blobmeta_key_a9ed5760_uniq
    UNIQUE (key);
CREATE INDEX blobs_blobm_expires_64b92d_partial
    ON public.blobs_blobmeta_tbl USING btree (expires_on) WHERE (expires_on IS NOT NULL);
CREATE INDEX blobs_blobmeta_parent_id_type_code_name_9a2a0a9e_idx
    ON public.blobs_blobmeta_tbl USING btree (parent_id, type_code, name);
ALTER TABLE blobs_blobmeta_tbl ADD CONSTRAINT blobs_blobmeta_type_code_check
    CHECK (type_code >= 0);
ALTER TABLE blobs_blobmeta_tbl ADD CONSTRAINT blobs_blobmeta_content_length_check
    CHECK (content_length >= 0);

COMMIT;
"""


# Expected output is all rows having DELETED status (no rows with KEPT status).
fix_bad_blobmeta_copies = """
WITH blobs AS (
    -- get rows with negative id (should be very few of these)
    -- use CTE to work around bad query plan in comp query
    SELECT * FROM blobs_blobmeta_tbl WHERE id < 0
),

deleted AS (
    -- delete where duplicate attachment from old form is associated with new form
    DELETE FROM blobs_blobmeta_tbl
    USING blobs
    INNER JOIN form_processor_xforminstancesql new_form
        ON new_form.form_id = blobs.parent_id AND new_form.domain = blobs.domain
    INNER JOIN form_processor_xformattachmentsql att ON att.id = -blobs.id
    INNER JOIN form_processor_xforminstancesql old_form
        ON old_form.form_id = att.form_id AND old_form.domain = blobs.domain
    WHERE blobs_blobmeta_tbl.id = blobs.id
        AND blobs.parent_id != att.form_id
        AND old_form.orig_id = blobs.parent_id
        AND new_form.deprecated_form_id = att.form_id
        AND blobs.name = att.name
        AND blobs.key = att.blob_id
        AND blobs.type_code = 2
        AND blobs.content_type = att.content_type
        AND blobs.content_length = att.content_length
    RETURNING blobs_blobmeta_tbl.*
)

SELECT 'DELETED' AS "status", * FROM deleted
UNION
SELECT 'KEPT' AS "status", * FROM blobs_blobmeta_tbl
WHERE id < 0 AND id NOT IN (SELECT id FROM deleted)
"""

# Expected output is updated rows, including with original form id.
fix_bad_form_attachment_reparenting = """
    WITH forms AS (
        -- CTE reduces number of rows that must be considered in,
        -- UPDATE WHERE clause below, a major optimization.
        SELECT *
        FROM form_processor_xforminstancesql form
        WHERE form.server_modified_on BETWEEN '2018-11-25' AND '2018-12-02'
        AND form.deprecated_form_id IS NOT NULL
    )
    UPDATE form_processor_xformattachmentsql upatt
    SET form_id = form.deprecated_form_id
    FROM forms form
    WHERE form.form_id = upatt.form_id
    AND EXISTS (
        -- form has at least one old-style attachment
        SELECT 1
        FROM form_processor_xformattachmentsql att
        WHERE att.form_id = form.form_id
    )
    AND EXISTS (
        -- form has at least one new-style attachment
        SELECT 1
        FROM blobs_blobmeta_tbl blob
        WHERE blob.parent_id = form.form_id
    )
    AND NOT EXISTS (
        -- deprecated form has no old-style attachments
        SELECT 1
        FROM form_processor_xformattachmentsql depr
        WHERE depr.form_id = form.deprecated_form_id
    )
    AND NOT EXISTS (
        -- deprecated form has no new-style attachments
        SELECT 1
        FROM blobs_blobmeta_tbl depr
        WHERE depr.parent_id = form.deprecated_form_id
    )
    RETURNING form.form_id AS old_form_id, upatt.*
"""


TEMPLATES = {
    "blobmeta_key": blobmeta_key,
    "blobmeta_forms": blobmeta_forms,
    "fix_bad_blobmeta_copies": fix_bad_blobmeta_copies,
    "fix_bad_form_attachment_reparenting": fix_bad_form_attachment_reparenting,
    "simple_move_form_attachments_to_blobmeta": simple_move_form_attachments_to_blobmeta,
    "move_form_attachments_to_blobmeta": move_form_attachments_to_blobmeta,
    "delete_dup_form_attachments": delete_dup_form_attachments,
    "show_invalid_indexes": show_invalid_indexes,

    # use to verify tables are empty
    # warning, may be slow (requires a table scan) if the table has many records
    "count_form_attachments":
        "SELECT COUNT(*) FROM form_processor_xformattachmentsql;"
}
