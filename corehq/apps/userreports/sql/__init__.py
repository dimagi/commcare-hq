from .adapter import get_indicator_table, IndicatorSqlAdapter, metadata
from .columns import get_expanded_column_config, SqlColumnConfig
from .util import get_column_name, get_table_name, truncate_value


import sqlalchemy
from django.conf import settings
from corehq.apps.userreports.sql.columns import column_to_sql


def get_engine():
    return sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)




