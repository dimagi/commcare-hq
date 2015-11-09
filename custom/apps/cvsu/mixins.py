import itertools

from sqlagg.columns import MonthColumn, YearColumn, YearQuarterColumn
from sqlagg.filters import IN

from corehq.apps.reports.sqlreport import SqlReportException, AggregateColumn, DatabaseColumn
from corehq.db import connection_manager
from custom.apps.cvsu.sqldata import combine_month_year, format_date, combine_quarter_year, format_year


class CVSUSqlDataMixin(object):

    def _find_column_view(self, column_name):
        for column in self.columns:
            if isinstance(column, AggregateColumn):
                for c in column.view.columns:
                    if c.name == column_name:
                        return c
            elif column.slug == column_name:
                return column.view

    def _find_column(self, column_name):
        for column in self.columns:
            if column.slug == column_name:
                return column

    def _get_data(self, slugs=None):
        if self.keys is not None and not self.group_by:
            raise SqlReportException('Keys supplied without group_by.')

        qc = self.query_context
        for c in self.columns:
            if not slugs or c.slug in slugs:
                qc.append_column(c.view)

        session = connection_manager.get_scoped_session(self.engine_id)

        try:
            for qm in qc.query_meta.values():
                date_aggregation_column = None
                if len(qm.columns) == 1:
                    c = self._find_column(qm.columns[0].column_name)
                    if hasattr(c, 'date_aggregation_column'):
                        date_aggregation_column = c.date_aggregation_column
                columns_names = itertools.chain.from_iterable([(col.column_name, col.alias) for col in qm.columns])
                for group_by in self.group_by:
                    if group_by not in columns_names:
                        column = self._find_column_view(group_by)
                        if column:
                            if date_aggregation_column:
                                column.key = date_aggregation_column
                                column.sql_column.column_name = date_aggregation_column
                            qm.append_column(column)

            return qc.resolve(session.connection(), self.filter_values)
        except:
            session.rollback()
            raise


class DateColumnMixin(object):

    @property
    def date_column(self):
        if self.grouping == 'month':
            return AggregateColumn(
                "Month", combine_month_year,
                [YearColumn('date_reported', alias='year'), MonthColumn('date_reported', alias='month')],
                format_fn=format_date)
        elif self.grouping == 'quarter':
            return AggregateColumn(
                "Quarter", combine_quarter_year,
                [YearColumn('date_reported', alias='year'), YearQuarterColumn('date_reported', alias='quarter')],
                format_fn=format_date)
        else:
            return DatabaseColumn("Year", YearColumn('date_reported', alias='year'), format_fn=format_year)


class FilterMixin(object):
    @property
    def filters(self):
        if not self.group_by_district:
            return[IN("user_id", "users")]

        return []
