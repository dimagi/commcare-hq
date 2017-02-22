from django.utils.translation import ugettext as _
import sqlalchemy
from sqlalchemy.exc import IntegrityError, ProgrammingError
from corehq.apps.userreports.adapter import IndicatorAdapter
from corehq.apps.userreports.exceptions import (
    ColumnNotFoundError, TableRebuildError, TableNotFoundWarning,
)
from corehq.apps.userreports.sql.columns import column_to_sql
from corehq.apps.userreports.sql.connection import get_engine_id
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import connection_manager
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception


metadata = sqlalchemy.MetaData()


class IndicatorSqlAdapter(IndicatorAdapter):

    def __init__(self, config):
        super(IndicatorSqlAdapter, self).__init__(config)
        self.engine_id = get_engine_id(config)
        self.session_helper = connection_manager.get_session_helper(self.engine_id)
        self.engine = self.session_helper.engine

    @memoized
    def get_table(self):
        return get_indicator_table(self.config)

    def rebuild_table(self):
        self.session_helper.Session.remove()
        try:
            rebuild_table(self.engine, self.get_table())
        except ProgrammingError as e:
            raise TableRebuildError('problem rebuilding UCR table {}: {}'.format(self.config, e))
        finally:
            self.session_helper.Session.commit()

    def build_table(self):
        self.session_helper.Session.remove()
        try:
            build_table(self.engine, self.get_table())
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
            self.get_table().drop(connection, checkfirst=True)

    def refresh_table(self):
        # SQL is always fresh
        pass

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

    def best_effort_save(self, doc):
        try:
            self.save(doc)
        except IntegrityError:
            pass  # can be due to users messing up their tables/data so don't bother logging
        except Exception as e:
            self.handle_exception(doc, e)

    def save(self, doc):
        """
        Saves the document. Should bubble up known errors.
        """
        indicator_rows = self.config.get_all_values(doc)
        if indicator_rows:
            table = self.get_table()
            with self.engine.begin() as connection:
                # delete all existing rows for this doc to ensure we aren't left with stale data
                delete = table.delete(table.c.doc_id == doc['_id'])
                connection.execute(delete)
                for indicator_row in indicator_rows:
                    all_values = {i.column.database_column_name: i.value for i in indicator_row}
                    insert = table.insert().values(**all_values)
                    connection.execute(insert)

    def delete(self, doc):
        table = self.get_table()
        with self.engine.begin() as connection:
            delete = table.delete(table.c.doc_id == doc['_id'])
            connection.execute(delete)


class ErrorRaisingIndicatorSqlAdapter(IndicatorSqlAdapter):

    def handle_exception(self, doc, exception):
        if isinstance(exception, ProgrammingError):
            orig = getattr(exception, 'orig')
            if orig:
                error_code = getattr(orig, 'pgcode')
                if error_code == '42P01':  # http://www.postgresql.org/docs/9.4/static/errcodes-appendix.html
                    raise TableNotFoundWarning

        super(ErrorRaisingIndicatorSqlAdapter, self).handle_exception(doc, exception)


def get_indicator_table(indicator_config, custom_metadata=None):
    sql_columns = [column_to_sql(col) for col in indicator_config.get_columns()]
    table_name = get_table_name(indicator_config.domain, indicator_config.table_id)
    # todo: needed to add extend_existing=True to support multiple calls to this function for the same table.
    # is that valid?
    return sqlalchemy.Table(
        table_name,
        custom_metadata or metadata,
        extend_existing=True,
        *sql_columns
    )


def rebuild_table(engine, table):
    with engine.begin() as connection:
        table.drop(connection, checkfirst=True)
        table.create(connection)


def build_table(engine, table):
    with engine.begin() as connection:
        table.create(connection, checkfirst=True)
