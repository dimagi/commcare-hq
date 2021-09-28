import hashlib
import itertools
import logging

from django.utils.translation import ugettext as _

import psycopg2
import sqlalchemy
from memoized import memoized
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Index, PrimaryKeyConstraint

from corehq.apps.userreports.adapter import IndicatorAdapter
from corehq.apps.userreports.exceptions import (
    ColumnNotFoundError,
    TableRebuildError,
    translate_programming_error,
)
from corehq.apps.userreports.sql.columns import column_to_sql
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import connection_manager
from corehq.util.soft_assert import soft_assert
from corehq.util.test_utils import unit_testing_only

logger = logging.getLogger(__name__)


engine_metadata = {}


def get_metadata(engine_id):
    return engine_metadata.setdefault(engine_id, sqlalchemy.MetaData())


class IndicatorSqlAdapter(IndicatorAdapter):

    def __init__(self, config, override_table_name=None, engine_id=None):
        super(IndicatorSqlAdapter, self).__init__(config)
        self.engine_id = engine_id or config.engine_id
        self.session_helper = connection_manager.get_session_helper(self.engine_id)
        self.session_context = self.session_helper.session_context
        self.engine = self.session_helper.engine
        self.override_table_name = override_table_name

    @property
    def table_id(self):
        return self.config.table_id

    @property
    def display_name(self):
        return self.config.display_name

    @memoized
    def get_table(self):
        return get_indicator_table(
            self.config, get_metadata(self.engine_id), override_table_name=self.override_table_name
        )

    @property
    def table_exists(self):
        return self.engine.has_table(self.get_table().name)

    @memoized
    def get_sqlalchemy_orm_table(self):
        table = self.get_table()
        Base = declarative_base(metadata=get_metadata(self.engine_id))

        class TemporaryTableDef(Base):
            __table__ = table

        return TemporaryTableDef

    def _apply_sql_addons(self):
        if self.config.sql_settings.citus_config.distribution_type:
            self._distribute_table()

    def _distribute_table(self):
        config = self.config.sql_settings.citus_config
        self.session_helper.Session.remove()
        if not self.session_helper.is_citus_db:
            # only do this if the database contains the citus extension
            return

        from custom.icds_core.db import create_citus_reference_table
        from custom.icds_core.db import create_citus_distributed_table
        with self.engine.begin() as connection:
            if config.distribution_type == 'hash':
                if config.distribution_column not in self.get_table().columns:
                    raise ColumnNotFoundError("Column '{}' not found.".format(config.distribution_column))
                create_citus_distributed_table(connection, self.get_table().name, config.distribution_column)
            elif config.distribution_type == 'reference':
                create_citus_reference_table(connection, self.get_table().name)
            else:
                raise ValueError("unknown distribution type: %r" % config.distribution_type)
            return True

    def rebuild_table(self, initiated_by=None, source=None, skip_log=False, diffs=None):
        self.log_table_rebuild(initiated_by, source, skip=skip_log, diffs=diffs)
        self.session_helper.Session.remove()
        try:
            rebuild_table(self.engine, self.get_table())
            self._apply_sql_addons()
        except (ProgrammingError, OperationalError) as e:
            raise TableRebuildError('problem rebuilding UCR table {}: {}'.format(self.config, e))
        finally:
            self.session_helper.Session.commit()

    def build_table(self, initiated_by=None, source=None):
        self.log_table_build(initiated_by, source)
        self.session_helper.Session.remove()
        try:
            build_table(self.engine, self.get_table())
            self._apply_sql_addons()
        except (ProgrammingError, OperationalError) as e:
            raise TableRebuildError('problem building UCR table {}: {}'.format(self.config, e))
        finally:
            self.session_helper.Session.commit()

    def drop_table(self, initiated_by=None, source=None, skip_log=False):
        self.log_table_drop(initiated_by, source, skip_log)
        # this will hang if there are any open sessions, so go ahead and close them
        self.session_helper.Session.remove()
        with self.engine.begin() as connection:
            table = self.get_table()
            table.drop(connection, checkfirst=True)
            get_metadata(self.engine_id).remove(table)

    @unit_testing_only
    def clear_table(self):
        table = self.get_table()
        with self.engine.begin() as connection:
            delete = table.delete()
            connection.execute(delete)

    def get_query_object(self):
        """
        Get a sqlalchemy query object ready to query this table
        """
        return self.session_helper.Session.query(self.get_table())

    def get_distinct_values(self, column, limit):
        too_many_values = False
        table = self.get_table()
        if not table.exists(bind=self.engine):
            return [], False

        if column not in table.c:
            raise ColumnNotFoundError(_(
                'The column "{}" does not exist in the report source! '
                'Please double check your report configuration.').format(column)
            )
        column = table.c[column]

        query = self.session_helper.Session.query(column).order_by(column).limit(limit + 1).distinct()
        result = query.all()
        distinct_values = [x[0] for x in result]
        if len(distinct_values) > limit:
            distinct_values = distinct_values[:limit]
            too_many_values = True

        return distinct_values, too_many_values

    def _best_effort_save_rows(self, rows, doc):
        try:
            self.save_rows(rows)
        except Exception as e:
            self.handle_exception(doc, e)

    def save_rows(self, rows, use_shard_col=True):
        """
        Saves rows to a data source after deleting the old rows
        :param use_shard_col: use shard column along with doc id for searching rows to delete/update
        """
        if not rows:
            return

        # transform format from ColumnValue to dict
        formatted_rows = [
            {i.column.database_column_name.decode('utf-8'): i.value for i in row}
            for row in rows
        ]
        if self.session_helper.is_citus_db and use_shard_col:
            config = self.config.sql_settings.citus_config
            if config.distribution_type == 'hash':
                self._by_column_update(formatted_rows)
                return
        doc_ids = set(row['doc_id'] for row in formatted_rows)
        table = self.get_table()
        if self.supports_upsert() and use_shard_col:
            queries = [self._upsert_query(table, formatted_rows)]
        else:
            delete = table.delete().where(table.c.doc_id.in_(doc_ids))
            # Using session.bulk_insert_mappings below might seem more inline
            #   with sqlalchemy API, but it results in
            #   appending an empty row which results in a postgres
            #   not-null constraint error, which has been hard to debug.
            # In addition, bulk_insert_mappings is less performant than
            #   the plain INSERT INTO VALUES statement resulting from below line
            #   because bulk_insert_mappings is meant for multi-table insertion
            #   so it has overhead of format conversions and multiple statements
            insert = table.insert().values(formatted_rows)
            queries = [delete, insert]
        with self.session_context() as session:
            for query in queries:
                session.execute(query)

    def _by_column_update(self, rows):
        config = self.config.sql_settings.citus_config
        shard_col = config.distribution_column
        table = self.get_table()

        rows = sorted(rows, key=lambda row: row[shard_col])
        for shard_value, rows_ in itertools.groupby(rows, key=lambda row: row[shard_col]):
            formatted_rows = list(rows_)
            doc_ids = set(row['doc_id'] for row in formatted_rows)
            if self.supports_upsert():
                queries = [self._upsert_query(table, formatted_rows)]
            else:
                delete = table.delete().where(table.c.get(shard_col) == shard_value)
                delete = delete.where(table.c.doc_id.in_(doc_ids))
                insert = table.insert().values(formatted_rows)
                queries = [delete, insert]

            with self.session_context() as session:
                for query in queries:
                    session.execute(query)

    def supports_upsert(self):
        """Return True if supports UPSERTS else False

        Assumes that neither a distribution column (citus) nor doc_id can change.
        """
        if self.session_helper.is_citus_db:
            # distribution_column and doc_id
            return len(self.config.pk_columns) == 2

        # doc_id
        return len(self.config.pk_columns) == 1

    def _upsert_query(self, table, rows):
        from sqlalchemy.dialects.postgresql import insert
        upsert = insert(table).values(rows)
        return upsert.on_conflict_do_update(
            constraint=table.primary_key,
            set_={
                col.name: col for col in upsert.excluded if not col.primary_key
            }
        )

    def bulk_save(self, docs):
        rows = []
        for doc in docs:
            rows.extend(self.get_all_values(doc))
        self.save_rows(rows)

    def bulk_delete(self, docs, use_shard_col=True):
        if self.session_helper.is_citus_db and use_shard_col:
            config = self.config.sql_settings.citus_config
            if config.distribution_type == 'hash':
                self._citus_bulk_delete(docs, config.distribution_column)
                return
        table = self.get_table()
        doc_ids = [doc['_id'] for doc in docs]
        delete = table.delete(table.c.doc_id.in_(doc_ids))
        with self.session_context() as session:
            session.execute(delete)

    def _citus_bulk_delete(self, docs, column):
        """
        When a delete is run on a distrbuted table, it grabs an exclusive write
        lock on the entire table unless the shard column is also provided.

        This function performs extra work to get the shard column so we are not
        blocked on deletes.
        """

        # these doc types were blocking the queue but the approach could be applied
        # more generally with some more testing
        SHARDABLE_DOC_TYPES = ('XFormArchived', 'XFormDeprecated', 'XFormDuplicate', 'XFormError')
        table = self.get_table()
        doc_ids_to_delete = []

        for doc in docs:
            if doc.get('doc_type') in SHARDABLE_DOC_TYPES:
                # get_all_values ignores duplicate and archived forms because
                # the implicit filtering on all data sources filters doc_types
                # get_all_values saves no changes to the original doc database
                # so we change the doc_type locally to get the sharded column

                tmp_doc = doc.copy()
                tmp_doc['doc_type'] = 'XFormInstance'
                rows = self.get_all_values(tmp_doc)
                if rows:
                    first_row = rows[0]
                    sharded_column_value = [
                        i.value for i in first_row
                        if i.column.database_column_name.decode('utf-8') == column
                    ]
                    if sharded_column_value:
                        delete = table.delete().where(table.c.doc_id == doc['_id'])
                        delete = delete.where(table.c.get(column) == sharded_column_value[0])
                        with self.session_context() as session:
                            session.execute(delete)
                        continue  # skip adding doc ID into doc_ids_to_delete

            doc_ids_to_delete.append(doc['_id'])

        if doc_ids_to_delete:
            delete = table.delete().where(table.c.doc_id.in_(doc_ids_to_delete))
            with self.session_context() as session:
                session.execute(delete)

    def delete(self, doc, use_shard_col=True):
        self.bulk_delete([doc], use_shard_col)

    def doc_exists(self, doc):
        with self.session_context() as session:
            query = session.query(self.get_table()).filter_by(doc_id=doc['_id'])
            return session.query(query.exists()).scalar()


class MultiDBSqlAdapter(object):

    mirror_adapter_cls = IndicatorSqlAdapter

    def __init__(self, config, override_table_name=None):
        config.validate_db_config()
        self.config = config
        self.main_adapter = self.mirror_adapter_cls(config, override_table_name)
        self.all_adapters = [self.main_adapter]
        engine_ids = self.config.mirrored_engine_ids
        for engine_id in engine_ids:
            self.all_adapters.append(self.mirror_adapter_cls(config, override_table_name, engine_id))

    def __getattr__(self, attr):
        return getattr(self.main_adapter, attr)

    @property
    def table_id(self):
        return self.config.table_id

    @property
    def display_name(self):
        return self.config.display_name

    def best_effort_save(self, doc, eval_context=None):
        for adapter in self.all_adapters:
            adapter.best_effort_save(doc, eval_context)

    def save(self, doc, eval_context=None):
        for adapter in self.all_adapters:
            adapter.save(doc, eval_context)

    def get_all_values(self, doc, eval_context=None):
        return self.config.get_all_values(doc, eval_context)

    @property
    def run_asynchronous(self):
        return self.config.asynchronous

    def get_distinct_values(self, column, limit):
        return self.main_adapter.get_distinct_values(column, limit)

    def build_table(self, initiated_by=None, source=None):
        for adapter in self.all_adapters:
            adapter.build_table(initiated_by=initiated_by, source=source)

    def rebuild_table(self, initiated_by=None, source=None, skip_log=False, diffs=None):
        for adapter in self.all_adapters:
            adapter.rebuild_table(initiated_by=initiated_by, source=source, skip_log=skip_log, diffs=diffs)

    def drop_table(self, initiated_by=None, source=None, skip_log=False):
        for adapter in self.all_adapters:
            adapter.drop_table(initiated_by=initiated_by, source=source, skip_log=skip_log)

    @unit_testing_only
    def clear_table(self):
        for adapter in self.all_adapters:
            adapter.clear_table()

    def save_rows(self, rows, use_shard_col=True):
        for adapter in self.all_adapters:
            adapter.save_rows(rows, use_shard_col)

    def bulk_save(self, docs):
        for adapter in self.all_adapters:
            adapter.bulk_save(docs)

    def bulk_delete(self, docs, use_shard_col=True):
        for adapter in self.all_adapters:
            adapter.bulk_delete(docs, use_shard_col)

    def doc_exists(self, doc):
        return any([
            adapter.doc_exists(doc)
            for adapter in self.all_adapters
        ])


class ErrorRaisingIndicatorSqlAdapter(IndicatorSqlAdapter):

    def handle_exception(self, doc, exception):
        ex = translate_programming_error(exception)
        if ex is not None:
            raise ex

        orig_exception = getattr(exception, 'orig', None)
        if orig_exception and isinstance(orig_exception, psycopg2.IntegrityError):
            if orig_exception.pgcode == psycopg2.errorcodes.NOT_NULL_VIOLATION:
                from corehq.apps.userreports.models import InvalidUCRData
                InvalidUCRData.objects.create(
                    doc_id=doc['_id'],
                    doc_type=doc['doc_type'],
                    domain=doc['domain'],
                    indicator_config_id=self.config._id,
                    validation_name='not_null_violation',
                    validation_text='A column in this doc violates an is_nullable constraint'
                )
                return

        super(ErrorRaisingIndicatorSqlAdapter, self).handle_exception(doc, exception)


class ErrorRaisingMultiDBAdapter(MultiDBSqlAdapter):
    mirror_adapter_cls = ErrorRaisingIndicatorSqlAdapter


def get_indicator_table(indicator_config, metadata, override_table_name=None):
    sql_columns = [column_to_sql(col) for col in indicator_config.get_columns()]
    table_name = override_table_name or get_table_name(indicator_config.domain, indicator_config.table_id)
    columns_by_col_id = {col.database_column_name.decode('utf-8') for col in indicator_config.get_columns()}
    extra_indices = []

    citus_config = indicator_config.sql_settings.citus_config
    if citus_config.distribution_type == 'hash':
        # Create hash index on doc_id for distributed tables
        extra_indices.append(Index(
            _custom_index_name(table_name, ['doc_id']),
            'doc_id',
            postgresql_using='hash'
        ))

    for index in indicator_config.sql_column_indexes:
        if set(index.column_ids).issubset(columns_by_col_id):
            extra_indices.append(Index(
                _custom_index_name(table_name, index.column_ids),
                *index.column_ids
            ))
        else:
            logger.error(f"Invalid index specified on {table_name} ({index.column_ids})")
    constraints = [PrimaryKeyConstraint(*indicator_config.pk_columns)]
    columns_and_indices = sql_columns + extra_indices + constraints
    current_table = metadata.tables.get(table_name)
    if current_table is not None:
        metadata.remove(current_table)
    return sqlalchemy.Table(
        table_name,
        metadata,
        *columns_and_indices
    )


def _custom_index_name(table_name, column_ids):
    base_name = "ix_{}_{}".format(table_name, ','.join(column_ids))
    base_hash = hashlib.md5(base_name.encode('utf-8')).hexdigest()
    return "{}_{}".format(base_name[:50], base_hash[:5])


def rebuild_table(engine, table):
    with engine.begin() as connection:
        table.drop(connection, checkfirst=True)
        table.create(connection)


def build_table(engine, table):
    with engine.begin() as connection:
        table.create(connection, checkfirst=True)
