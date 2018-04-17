"""
Use this in preparation ``for form_processor/0067_auto_20170915_1506.py`` migration
"""

from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from itertools import groupby

from django.core.management.base import BaseCommand
from django.db import connections

from corehq.form_processor.models import CommCareCaseIndexSQL
from corehq.form_processor.utils.sql import fetchall_as_namedtuple, fetchone_as_namedtuple
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from dimagi.utils.chunked import chunked
import six


IDENTIFIER_INDEX_NAME = 'form_processor_commcarecaseindexsql_identifier'
UNIQIE_INDEX_NAME = "form_processor_commcarecaseindexsql_case_id_57ebda3c_uniq"


def log_sql_verbose(sql):
    print('\n    {}\n'.format(sql))


def log_sql(sql):
    pass


class Command(BaseCommand):
    def handle(self, **options):
        verbose = options['verbosity'] >= 2
        if verbose:
            global log_sql
            log_sql = log_sql_verbose

        for db in get_db_aliases_for_partitioned_query():
            if _index_exists(db, UNIQIE_INDEX_NAME):
                print(self.style.SUCCESS('Unique index already exists on db: {}'.format(db)))
                continue

            _add_temp_index(db)

            case_ids = _get_case_ids_with_dupe_indices(db)
            attempts = 0
            while case_ids and attempts < 3:
                attempts += 1
                print('{} cases found with duplicate indices. DB: {}, attempt: {}'.format(
                    len(case_ids), db, attempts)
                )
                _delete_duplicate_indices(case_ids, db)
                case_ids = _get_case_ids_with_dupe_indices(db)

            if case_ids:
                print(self.style.ERROR(
                    '{} cases still have duplicate '
                    'indices after 3 attempts for db: {}'.format(len(case_ids), db))
                )
                grouped_indices = groupby(
                    CommCareCaseIndexSQL.objects.using(db)
                    .filter(case_id__in=case_ids), key=lambda c: c.case_id
                )
                for case_id, indices in grouped_indices:
                    print('--> Case: {}\n'.format(case_id))
                    print('    {}'.format('\n    '.join(six.text_type(i) for i in indices)))
                print('\n')
            else:
                print(self.style.WARNING('Attempting to create unique index and constraint for db: {}'.format(db)))
                try:
                    _add_unique_constraint_to_case_index_table(db)
                except Exception as e:
                    print(self.style.ERROR('Failed to create unique constraint on DB {}: {}'.format(db, e)))
                    print(self.style.WARNING('Temporary index left in place'))
                else:
                    print(self.style.SUCCESS('Unique constraint added to db {}'.format(db)))
                    _drop_index(db, IDENTIFIER_INDEX_NAME)


def _add_temp_index(db):
    """Add an index to the 'identifier' column to make queries faster."""
    add_identifier_index = """
        CREATE INDEX CONCURRENTLY {identifier_index_name} ON {case_index_table} (identifier)
    """.format(
        case_index_table=CommCareCaseIndexSQL._meta.db_table,
        identifier_index_name=IDENTIFIER_INDEX_NAME
    )
    with connections[db].cursor() as cursor:
        if not _index_exists(db, IDENTIFIER_INDEX_NAME):
            log_sql(add_identifier_index)
            cursor.execute(add_identifier_index)


def _index_exists(db, index_name):
    with connections[db].cursor() as cursor:
        sql = "SELECT to_regclass('{}') IS NOT NULL as index_exists".format(index_name)
        log_sql(sql)
        cursor.execute(sql)
        return fetchone_as_namedtuple(cursor).index_exists


def _drop_index(db, index_name):
    """Drop the index if it exists"""
    drop_identifier_index = """
            DROP INDEX CONCURRENTLY IF EXISTS {index_name}
        """.format(index_name=index_name)
    with connections[db].cursor() as cursor:
        log_sql(drop_identifier_index)
        cursor.execute(drop_identifier_index)


def _add_unique_constraint_to_case_index_table(db):
    """This will add a unique index concurrently and also a table constraint that uses the index.
    The result will be the same as adding a 'unique_together' option in the Django model.
    """
    create_index_sql = """
        CREATE UNIQUE INDEX CONCURRENTLY {index_name} on {case_index_table} ("case_id", "identifier")
    """.format(
        case_index_table=CommCareCaseIndexSQL._meta.db_table,
        index_name=UNIQIE_INDEX_NAME,
    )

    add_constraint_sql = """
        ALTER TABLE {case_index_table} ADD CONSTRAINT {index_name} UNIQUE USING INDEX {index_name}
    """.format(
        case_index_table=CommCareCaseIndexSQL._meta.db_table,
        index_name=UNIQIE_INDEX_NAME,
    )

    try:
        with connections[db].cursor() as cursor:
            log_sql(create_index_sql)
            cursor.execute(create_index_sql)
            log_sql(add_constraint_sql)
            cursor.execute(add_constraint_sql)
    except:
        # if the index creation failed make sure we remove it otherwise we
        # are left with an invalid index
        _drop_index(db, UNIQIE_INDEX_NAME)
        raise


def _delete_duplicate_indices(case_ids, db):
    """Delete duplicate indices on cases only if they point to the same target case and
    have the same identifier and relationship"""
    delete_dupes_sql = """
        DELETE FROM {case_index_table} WHERE id in (
        SELECT id FROM (
          SELECT id, case_id, row_number() OVER (PARTITION BY case_id, identifier, referenced_id, relationship_id)
          FROM {case_index_table} JOIN (SELECT UNNEST(ARRAY['{{case_ids}}']) AS case_id) AS cx USING (case_id)) as indices
        WHERE row_number > 1
        )
    """.format(case_index_table=CommCareCaseIndexSQL._meta.db_table)

    for chunk in chunked(case_ids, 100):
        with connections[db].cursor() as cursor:
            delete_sql = delete_dupes_sql.format(case_ids="','".join(chunk))
            log_sql(delete_sql)
            cursor.execute(delete_sql)


def _get_case_ids_with_dupe_indices(db):
    """Get case_ids that have duplicate indices (same identifier)
    """
    case_id_with_dupes_sql = """
        SELECT case_id, identifier, count(*)
        FROM {case_index_table}
        GROUP BY case_id, identifier
        HAVING count(*) > 1
    """.format(case_index_table=CommCareCaseIndexSQL._meta.db_table)

    with connections[db].cursor() as cursor:
        log_sql(case_id_with_dupes_sql)
        cursor.execute(case_id_with_dupes_sql)
        rows_with_dupes = fetchall_as_namedtuple(cursor)
        case_ids = {row.case_id for row in rows_with_dupes}
    return case_ids
