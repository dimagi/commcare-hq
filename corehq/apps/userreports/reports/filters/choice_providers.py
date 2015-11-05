from sqlalchemy.exc import ProgrammingError
from corehq.apps.reports_core.filters import DynamicChoiceListFilter
from corehq.apps.userreports.sql import IndicatorSqlAdapter


DATA_SOURCE_COLUMN = 'data_source_column'


class ChoiceQueryContext(object):
    """
    Context that will be passed to a choice provider function.
    """
    def __init__(self, report, report_filter, query=None, limit=20, page=0):
        self.report = report
        self.report_filter = report_filter
        self.query = query
        self.limit = limit
        self.page = page

    @property
    def offset(self):
        return self.page * self.limit


def get_choices_from_data_source_column(query_context):
    # todo: we may want to log this as soon as mobile UCR stops hitting this
    # for misconfigured filters
    if not isinstance(query_context.report_filter, DynamicChoiceListFilter):
        return []

    adapter = IndicatorSqlAdapter(query_context.report.config)
    table = adapter.get_table()
    sql_column = table.c[query_context.report_filter.field]
    query = adapter.session_helper.Session.query(sql_column)
    if query_context.query:
        query = query.filter(sql_column.contains(query_context.query))

    try:
        return [
            {'value': v[0], 'display': v[0]}
            for v in query.distinct().order_by(sql_column).limit(query_context.limit).offset(query_context.offset)
        ]
    except ProgrammingError:
        return []
