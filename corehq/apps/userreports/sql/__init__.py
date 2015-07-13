from .columns import get_expanded_column_config, SqlColumnConfig
import hashlib
import sqlalchemy
from django.conf import settings
from sqlalchemy.exc import IntegrityError, ProgrammingError
from corehq.apps.userreports.exceptions import TableRebuildError
from corehq.apps.userreports.sql.columns import column_to_sql
from dimagi.utils.decorators.memoized import memoized


metadata = sqlalchemy.MetaData()


class IndicatorSqlAdapter(object):

    def __init__(self, engine, config):
        self.engine = engine
        self.config = config

    @memoized
    def get_table(self):
        return get_indicator_table(self.config)

    def rebuild_table(self):
        try:
            rebuild_table(self.engine, self.get_table())
        except ProgrammingError, e:
            raise TableRebuildError('problem rebuilding UCR table {}: {}'.format(self.config, e))

    def drop_table(self):
        with self.engine.begin() as connection:
            self.get_table().drop(connection, checkfirst=True)

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


def get_engine():
    return sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)


def rebuild_table(engine, table):
    with engine.begin() as connection:
        table.drop(connection, checkfirst=True)
        table.create(connection)
    engine.dispose()


def truncate_value(value, max_length=63):
    """
    Truncate a value (typically a column name) to a certain number of characters,
    using a hash to ensure uniqueness.
    """
    if len(value) > max_length:
        short_hash = hashlib.sha1(value).hexdigest()[:8]
        return '{}_{}'.format(value[-54:], short_hash)
    return value


def get_column_name(path):
    """
    :param path: xpath from form or case
    :return: column name for postgres

    Postgres only allows columns up to 63 characters
    Anyone viewing the table directly will want to know the last parts of the path, not the first parts e.g.
    this: 'my_long_choice_list_option_1_ABCDEFGH', 'my_long_choice_list_option_2_ABCD1234'
    not: 'question_group_1_my_long_choice_ABCDEFGH', 'question_group_1_my_long_choice_ABCD1234'
    """
    parts = path.split("/")

    def _hash(parts):
        front = "/".join(parts[:-1])
        end = parts[-1]
        return hashlib.sha1('{}_{}'.format(hashlib.sha1(front).hexdigest(), end)).hexdigest()[:8]

    new_parts = path[-54:].split("/")
    return "_".join(new_parts + [_hash(parts)])


def get_table_name(domain, table_id):
    def _hash(domain, table_id):
        return hashlib.sha1('{}_{}'.format(hashlib.sha1(domain).hexdigest(), table_id)).hexdigest()[:8]

    return 'config_report_{0}_{1}_{2}'.format(domain, table_id, _hash(domain, table_id))
