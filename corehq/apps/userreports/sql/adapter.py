from __future__ import absolute_import
from __future__ import unicode_literals

import hashlib
import logging

import sqlalchemy
from architect import install
from django.utils.translation import ugettext as _
from memoized import memoized
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Index, PrimaryKeyConstraint

from corehq.apps.userreports.adapter import IndicatorAdapter
from corehq.apps.userreports.exceptions import (
    ColumnNotFoundError, TableRebuildError, translate_programming_error)
from corehq.apps.userreports.sql.columns import column_to_sql
from corehq.apps.userreports.sql.connection import get_engine_id
from corehq.apps.userreports.sql.util import view_exists
from corehq.apps.userreports.util import get_table_name, get_legacy_table_name
from corehq.sql_db.connections import connection_manager
from corehq.util.soft_assert import soft_assert
from corehq.util.test_utils import unit_testing_only

logger = logging.getLogger(__name__)


metadata = sqlalchemy.MetaData()


class IndicatorSqlAdapter(IndicatorAdapter):

    def __init__(self, config):
        super(IndicatorSqlAdapter, self).__init__(config)
        self.engine_id = get_engine_id(config)
        self.session_helper = connection_manager.get_session_helper(self.engine_id)
        self.engine = self.session_helper.engine

    @property
    def table_id(self):
        return self.config.table_id

    @property
    def display_name(self):
        return self.config.display_name

    @memoized
    def get_table(self):
        return get_indicator_table(self.config)

    @memoized
    def get_sqlalchemy_orm_table(self):
        table = self.get_table()
        Base = declarative_base(metadata=metadata)

        class TemporaryTableDef(Base):
            __table__ = table

        return TemporaryTableDef

    def _apply_sql_addons(self):
        distributed = False
        if self.config.sql_settings.citus_config.distribution_type:
            distributed = self._distribute_table()

        if self.config.sql_settings.partition_config:
            if distributed:
                logger.warning(
                    'Skipping installing partitions since table is distributed in CitusDB: %s', self.table_id
                )
            else:
                self._install_partition()

    def _distribute_table(self):
        config = self.config.sql_settings.citus_config
        self.session_helper.Session.remove()
        if not self.session_helper.is_citus_db:
            # only do this if the database contains the citus extension
            return

        with self.engine.begin() as connection:
            if config.distribution_type == 'hash':
                if config.distribution_column not in self.get_table().columns:
                    raise ColumnNotFoundError("Column '{}' not found.".format(config.distribution_column))
                connection.execute("select create_distributed_table('{}', '{}')".format(
                    self.get_table().name, config.distribution_column
                ))
            elif config.distribution_type == 'reference':
                connection.execute("select create_reference_table('{}')".format(
                    self.get_table().name
                ))
            else:
                raise ValueError("unknown distribution type: %r" % config.distribution_type)
            return True

    def _install_partition(self):
        config = self.config.sql_settings.partition_config[0]
        partition = install(
            'partition', type='range', subtype=config.subtype,
            constraint=config.constraint, column=config.column, db=self.engine.url,
            orm='sqlalchemy', return_null=True
        )
        mapping = self.get_sqlalchemy_orm_table()
        partition(mapping)
        mapping.architect.partition.get_partition().prepare()

    def rebuild_table(self):
        self.session_helper.Session.remove()
        try:
            self._drop_legacy_table_and_view()
            rebuild_table(self.engine, self.get_table())
            self._apply_sql_addons()
        except ProgrammingError as e:
            raise TableRebuildError('problem rebuilding UCR table {}: {}'.format(self.config, e))
        finally:
            self.session_helper.Session.commit()

    def build_table(self):
        self.session_helper.Session.remove()
        try:
            self._drop_legacy_table_and_view()
            build_table(self.engine, self.get_table())
            self._apply_sql_addons()
        except ProgrammingError as e:
            raise TableRebuildError('problem building UCR table {}: {}'.format(self.config, e))
        finally:
            self.session_helper.Session.commit()

    def drop_table(self):
        # this will hang if there are any open sessions, so go ahead and close them
        self.session_helper.Session.remove()
        self._drop_legacy_table_and_view()
        with self.engine.begin() as connection:
            table = self.get_table()
            if self.config.sql_settings.partition_config:
                connection.execute('DROP TABLE "{tablename}" CASCADE'.format(tablename=table.name))
            else:
                table.drop(connection, checkfirst=True)
            metadata.remove(table)

    def _drop_legacy_table_and_view(self):
        legacy_table_name = get_legacy_table_name(self.config.domain, self.config.table_id)
        view_name = get_table_name(self.config.domain, self.config.table_id)
        with self.engine.begin() as connection:
            if view_exists(connection, view_name):
                # Can't use `DROP VIEW IF EXISTS` since PG raises an error if there ther
                # is a table with the same name
                connection.execute("""
                    DROP VIEW "{view}";
                    DROP TABLE "{table}" CASCADE
                """.format(view=view_name, table=legacy_table_name))

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

    def save_rows(self, rows):
        """
        Saves rows to a data source after deleting the old rows
        """
        if not rows:
            return

        # transform format from ColumnValue to dict
        formatted_rows = [
            {i.column.database_column_name.decode('utf-8'): i.value for i in row}
            for row in rows
        ]
        doc_ids = set(row['doc_id'] for row in formatted_rows)
        table = self.get_table()
        delete = table.delete(table.c.doc_id.in_(doc_ids))
        # Using session.bulk_insert_mappings below might seem more inline
        #   with sqlalchemy API, but it results in
        #   appending an empty row which results in a postgres
        #   not-null constraint error, which has been hard to debug.
        # In addition, bulk_insert_mappings is less performant than
        #   the plain INSERT INTO VALUES statement resulting from below line
        #   because bulk_insert_mappings is meant for multi-table insertion
        #   so it has overhead of format conversions and multiple statements
        insert = table.insert().values(formatted_rows)
        with self.session_helper.session_context() as session:
            session.execute(delete)
            session.execute(insert)

    def bulk_save(self, docs):
        rows = []
        for doc in docs:
            rows.extend(self.get_all_values(doc))
        self.save_rows(rows)

    def bulk_delete(self, doc_ids):
        table = self.get_table()
        delete = table.delete(table.c.doc_id.in_(doc_ids))
        with self.session_helper.session_context() as session:
            session.execute(delete)

    def delete(self, doc):
        table = self.get_table()
        delete = table.delete(table.c.doc_id == doc['_id'])
        with self.session_helper.session_context() as session:
            session.execute(delete)

    def doc_exists(self, doc):
        with self.session_helper.session_context() as session:
            query = session.query(self.get_table()).filter_by(doc_id=doc['_id'])
            return session.query(query.exists()).scalar()


class ErrorRaisingIndicatorSqlAdapter(IndicatorSqlAdapter):

    def handle_exception(self, doc, exception):
        ex = translate_programming_error(exception)
        if ex:
            raise ex
        super(ErrorRaisingIndicatorSqlAdapter, self).handle_exception(doc, exception)


def get_indicator_table(indicator_config, custom_metadata=None, override_table_name=None):
    sql_columns = [column_to_sql(col) for col in indicator_config.get_columns()]
    table_name = override_table_name or get_table_name(indicator_config.domain, indicator_config.table_id)
    columns_by_col_id = {col.database_column_name.decode('utf-8') for col in indicator_config.get_columns()}
    extra_indices = []
    for index in indicator_config.sql_column_indexes:
        if set(index.column_ids).issubset(columns_by_col_id):
            extra_indices.append(Index(
                _custom_index_name(table_name, index.column_ids),
                *index.column_ids
            ))
        else:
            _assert = soft_assert('{}@{}'.format('jemord', 'dimagi.com'))
            _assert(False, "Invalid index specified on {}".format(table_name))
            break
    constraints = [PrimaryKeyConstraint(*indicator_config.pk_columns)]
    columns_and_indices = sql_columns + extra_indices + constraints
    # todo: needed to add extend_existing=True to support multiple calls to this function for the same table.
    # is that valid?
    return sqlalchemy.Table(
        table_name,
        custom_metadata or metadata,
        extend_existing=True,
        *columns_and_indices
    )


def _custom_index_name(table_name, column_ids):
    base_name = "ix_{}_{}".format(table_name, ','.join(column_ids))
    base_hash = hashlib.md5(base_name.encode('utf-8')).hexdigest()
    return "{}_{}".format(base_name[:50], base_hash[:5])


def rebuild_table(engine, table):
    with engine.begin() as connection:
        table.drop(connection, checkfirst=True)
        metadata.remove(table)
        table.create(connection)


def build_table(engine, table):
    with engine.begin() as connection:
        table.create(connection, checkfirst=True)
