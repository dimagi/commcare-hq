from sqlalchemy.exc import ProgrammingError
from corehq.apps.reports_core.filters import DynamicChoiceListFilter
from corehq.apps.userreports.sql import IndicatorSqlAdapter


def get_choices_from_data_source_column(data_source, report_filter, search_term=None, limit=20, page=0):
    # todo: we may want to log this as soon as mobile UCR stops hitting this
    # for misconfigured filters
    if not isinstance(report_filter, DynamicChoiceListFilter):
        return []

    adapter = IndicatorSqlAdapter(data_source)
    table = adapter.get_table()
    sql_column = table.c[report_filter.field]
    query = adapter.session_helper.Session.query(sql_column)
    if search_term:
        query = query.filter(sql_column.contains(search_term))

    offset = page * limit
    try:
        return [{'value': v[0], 'display': v[0]}
                for v in query.distinct().order_by(sql_column).limit(limit).offset(offset)]
    except ProgrammingError:
        return []
