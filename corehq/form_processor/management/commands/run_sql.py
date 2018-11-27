"""Run SQL concurrently on partition databases

SQL statement templates may use the `{chunk_size}` placeholder, which
will be replaced with the value of the --chunk-size=N command argument.
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import sys
import traceback
from datetime import datetime, timedelta
from functools import wraps

import attr
import gevent
from django.core.management.base import BaseCommand
from django.db import connections
from six.moves import input

from corehq.sql_db.util import get_db_aliases_for_partitioned_query

MULTI_DB = 'Executing on ALL (%s) databases in parallel. Continue?'


class Command(BaseCommand):
    help = """Run SQL concurrently on partition databases."""

    def add_arguments(self, parser):
        parser.add_argument('name', choices=list(TEMPLATES), help="SQL statement name.")
        parser.add_argument('-d', '--dbname', help='Django DB alias to run on')
        parser.add_argument('--chunk-size', type=int, default=1000,
            help="Maximum number of records to move at once.")

    def handle(self, name, dbname, chunk_size, **options):
        template = TEMPLATES[name]
        sql = template.format(chunk_size=chunk_size)
        run = getattr(template, "run", run_once)
        dbnames = get_db_aliases_for_partitioned_query()
        if dbname or len(dbnames) == 1:
            run(sql, dbname or dbnames[0])
        elif not confirm(MULTI_DB % len(dbnames)):
            sys.exit('abort')
        else:
            greenlets = []
            for dbname in dbnames:
                g = gevent.spawn(run, sql, dbname)
                greenlets.append(g)

            gevent.joinall(greenlets)
            try:
                for job in greenlets:
                    job.get()
            except Exception:
                traceback.print_exc()


def confirm(msg):
    return input(msg + "\n(y/N) ").lower() == 'y'


def timed(func):
    @wraps(func)
    def timed(sql, dbname):
        print("running on %s database" % dbname)
        start = datetime.now()
        try:
            return func(sql, dbname)
        finally:
            print("{} elapsed: {}".format(dbname, datetime.now() - start))
    return timed


@timed
def run_once(sql, dbname):
    """Run sql statement once on database

    This is the default run mode for statements
    """
    with connections[dbname].cursor() as cursor:
        cursor.execute(sql)


@attr.s
class RunUntilZero(object):
    """SQL statement to be run repeatedly

    ...until the first column of the first returned row is zero.
    """

    sql = attr.ib()

    def format(self, **kw):
        return self.sql.format(**kw)

    @staticmethod
    @timed
    def run(sql, dbname):
        next_update = datetime.now()
        total = 0
        with connections[dbname].cursor() as cursor:
            while True:
                cursor.execute(sql)
                rows = cursor.fetchmany(2)
                assert len(rows) == 1 and len(rows[0]) == 1, \
                    "expected 1 row with 1 column, got %r" % (rows,)
                moved = rows[0][0]
                if not moved:
                    break
                total += moved
                now = datetime.now()
                if now > next_update:
                    print("{}: processed {} items".format(dbname, total))
                    next_update = now + timedelta(seconds=5)
        print("{} final: processed {} items".format(dbname, total))


# see https://github.com/dimagi/commcare-hq/pull/21631
BLOBMETA_KEY_SQL = """
CREATE INDEX CONCURRENTLY IF NOT EXISTS form_processor_xformattachmentsql_blobmeta_key
ON public.form_processor_xformattachmentsql (((
    CASE
        WHEN blob_bucket = '' THEN '' -- empty bucket -> blob_id is the key
        ELSE COALESCE(blob_bucket, 'form/' || REPLACE(attachment_id::text, '-', '')) || '/'
    END || blob_id
)::varchar(255)))
"""
DROP_BLOBMETA_KEY = "DROP INDEX form_processor_xformattachmentsql_blobmeta_key"
BLOBMETA_VIEW = """
CREATE OR REPLACE VIEW blobs_blobmeta AS
SELECT
    "id",
    "domain",
    "parent_id",
    "name",
    "key",
    "type_code",
    "content_type",
    "properties",
    "created_on",
    "expires_on",
    "content_length"
FROM blobs_blobmeta_tbl

UNION ALL

SELECT
    -att."id" AS "id",
    xform."domain",
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
    att.properties,
    xform.received_on AS created_on,
    NULL AS expires_on,
    att.content_length
FROM form_processor_xformattachmentsql att
    INNER JOIN form_processor_xforminstancesql xform
        ON xform.form_id = att.form_id;
"""


# Move rows incrementally.
# WARNING monitor disk usage when running in large environments.
# Does not require downtime, but may be slow.
MOVE_FORM_ATTACHMENTS = RunUntilZero("""
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


# move all rows in one go.
# requires table lock, so may not be feasible without some downtime.
# this may be necessary if MOVE_FORM_ATTACHMENTS is too slow.
BLOBMETA_FORMS_SQL = """
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


TEMPLATES = {
    "blobmeta_key": BLOBMETA_KEY_SQL,
    "blobmeta_forms": BLOBMETA_FORMS_SQL,
    "move_form_attachments_to_blobmeta": MOVE_FORM_ATTACHMENTS,

    # these will be used to fix staging, should not be necessary anywhere else
    "drop_blobmeta_key": DROP_BLOBMETA_KEY,
    "blobmeta_view": BLOBMETA_VIEW,
}
