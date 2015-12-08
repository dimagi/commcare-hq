import sqlalchemy
from sqlalchemy.exc import IntegrityError, ProgrammingError
from corehq.apps.userreports.exceptions import TableRebuildError
from corehq.apps.userreports.sql.columns import column_to_sql
from corehq.apps.userreports.sql.connection import get_engine_id
from corehq.apps.userreports.sql.util import get_table_name
from corehq.sql_db.connections import connection_manager
from dimagi.utils.decorators.memoized import memoized


metadata = sqlalchemy.MetaData()


class IndicatorSqlAdapter(object):

    def __init__(self, config):
        self.config = config
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
        except ProgrammingError, e:
            raise TableRebuildError('problem rebuilding UCR table {}: {}'.format(self.config, e))
        finally:
            self.session_helper.Session.commit()

    def drop_table(self):
        # this will hang if there are any open sessions, so go ahead and close them
        self.session_helper.Session.remove()
        with self.engine.begin() as connection:
            self.get_table().drop(connection, checkfirst=True)

    def get_query_object(self):
        """
        Get a sqlalchemy query object ready to query this table
        """
        return self.session_helper.Session.query(self.get_table())

    def save(self, doc):
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
                    try:
                        connection.execute(insert)
                    except IntegrityError:
                        # Someone beat us to it. Concurrent inserts can happen
                        # when a doc is processed by the celery rebuild task
                        # at the same time as the pillow.
                        pass

    def delete(self, doc):
        table = self.get_table()
        with self.engine.begin() as connection:
            delete = table.delete(table.c.doc_id == doc['_id'])
            connection.execute(delete)


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
