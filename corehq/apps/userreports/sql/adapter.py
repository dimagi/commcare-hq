from __future__ import absolute_import
from __future__ import unicode_literals
import hashlib
import six

from architect import install
from django.utils.translation import ugettext as _
import sqlalchemy
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Index

from corehq.apps.userreports.adapter import IndicatorAdapter
from corehq.apps.userreports.exceptions import (
    ColumnNotFoundError, TableRebuildError, TableNotFoundWarning,
    MissingColumnWarning)
from corehq.apps.userreports.sql.columns import column_to_sql
from corehq.apps.userreports.sql.connection import get_engine_id
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import connection_manager
from corehq.util.soft_assert import soft_assert
from corehq.util.test_utils import unit_testing_only
from memoized import memoized


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
    def get_sqlalchemy_mapping(self):
        table = self.get_table()
        Base = declarative_base(metadata=metadata)
        properties = dict(table.columns)
        properties['__tablename__'] = table.name
        properties['__table_args__'] = ({'extend_existing': True},)

        type_ = type("TemporaryTableDef" if six.PY3 else b"TemporaryTableDef", (Base,), properties)
        return type_

    def _install_partition(self):
        if self.config.sql_settings.partition_config:
            config = self.config.sql_settings.partition_config[0]
            partition = install(
                'partition', type='range', subtype=config.subtype,
                constraint=config.constraint, column=config.column, db=self.engine.url,
                orm='sqlalchemy'
            )
            mapping = self.get_sqlalchemy_mapping()
            partition(mapping)
            mapping.architect.partition.get_partition().prepare()

    def rebuild_table(self):
        self.session_helper.Session.remove()
        try:
            rebuild_table(self.engine, self.get_table())
            self._install_partition()
        except ProgrammingError as e:
            raise TableRebuildError('problem rebuilding UCR table {}: {}'.format(self.config, e))
        finally:
            self.session_helper.Session.commit()

    def build_table(self):
        self.session_helper.Session.remove()
        try:
            build_table(self.engine, self.get_table())
            self._install_partition()
        except ProgrammingError as e:
            raise TableRebuildError('problem building UCR table {}: {}'.format(self.config, e))
        finally:
            self.session_helper.Session.commit()

    def after_table_build(self):
        pass

    def drop_table(self):
        # this will hang if there are any open sessions, so go ahead and close them
        self.session_helper.Session.remove()
        with self.engine.begin() as connection:
            if self.config.sql_settings.partition_config:
                connection.execute('DROP TABLE "{tablename}" CASCADE'.format(tablename=self.get_table().name))
            else:
                self.get_table().drop(connection, checkfirst=True)

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
        except IntegrityError:
            pass  # can be due to users messing up their tables/data so don't bother logging
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
        if isinstance(exception, ProgrammingError):
            orig = getattr(exception, 'orig')
            if orig:
                error_code = getattr(orig, 'pgcode')
                # http://www.postgresql.org/docs/9.4/static/errcodes-appendix.html
                if error_code == '42P01':
                    raise TableNotFoundWarning
                elif error_code == '42703':
                    raise MissingColumnWarning

        super(ErrorRaisingIndicatorSqlAdapter, self).handle_exception(doc, exception)


def get_indicator_table(indicator_config, custom_metadata=None):
    sql_columns = [column_to_sql(col) for col in indicator_config.get_columns()]
    table_name = get_table_name(indicator_config.domain, indicator_config.table_id).decode('utf-8')
    columns_by_col_id = {col.database_column_name for col in indicator_config.get_columns()}
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
    columns_and_indices = sql_columns + extra_indices
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
    base_hash = hashlib.md5(base_name).hexdigest()
    return "{}_{}".format(base_name[:50], base_hash[:5])


def rebuild_table(engine, table):
    with engine.begin() as connection:
        table.drop(connection, checkfirst=True)
        table.create(connection)


def build_table(engine, table):
    with engine.begin() as connection:
        table.create(connection, checkfirst=True)
