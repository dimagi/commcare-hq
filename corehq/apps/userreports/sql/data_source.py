from __future__ import absolute_import
from __future__ import unicode_literals
import numbers

from django.utils.decorators import method_decorator
from django.utils.translation import ugettext

from dimagi.utils.decorators.memoized import memoized

from sqlagg.columns import SimpleColumn
from sqlagg.sorting import OrderBy

from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.userreports.decorators import catch_and_raise_exceptions
from corehq.apps.userreports.exceptions import InvalidQueryColumn
from corehq.apps.userreports.mixins import ConfigurableReportDataSourceMixin
from corehq.apps.userreports.reports.sorting import ASCENDING
from corehq.apps.userreports.reports.specs import CalculatedColumn
from corehq.apps.userreports.reports.util import get_expanded_columns
from corehq.apps.userreports.sql.connection import get_engine_id
from corehq.sql_db.connections import connection_manager


class ConfigurableReportSqlDataSource(ConfigurableReportDataSourceMixin, SqlData):
    @property
    def engine_id(self):
        return get_engine_id(self.config, allow_read_replicas=True)

    @property
    def filters(self):
        return [_f for _f in [fv.to_sql_filter() for fv in self._filter_values.values()] if _f]

    @property
    def filter_values(self):
        return {k: v for fv in self._filter_values.values() for k, v in fv.to_sql_values().items()}

    @property
    def order_by(self):
        # allow throwing exception if the report explicitly sorts on an unsortable column type
        if self._order_by:
            return [
                OrderBy(order_by, is_ascending=(order == ASCENDING))
                for sort_column_id, order in self._order_by
                for order_by in self.get_db_column_ids(sort_column_id)
            ]
        elif self.top_level_columns:
            try:
                return [
                    OrderBy(order_by, is_ascending=True)
                    for order_by in self.get_db_column_ids(self.top_level_columns[0].column_id)
                ]
            except InvalidQueryColumn:
                pass
        return []

    @property
    def columns(self):
        # This explicitly only includes columns that resolve to database queries.
        # The name is a bit confusing but is hard to change due to its dependency in SqlData
        db_columns = [c for c in self.inner_columns if not isinstance(c, CalculatedColumn)]
        fields = {c.slug for c in db_columns}

        return db_columns + [
            DatabaseColumn('', SimpleColumn(deferred_filter.field))
            for deferred_filter in self._deferred_filters.values()
            if deferred_filter.field not in fields]

    @memoized
    @method_decorator(catch_and_raise_exceptions)
    def get_data(self, start=None, limit=None):
        ret = super(ConfigurableReportSqlDataSource, self).get_data(start=start, limit=limit)

        for report_column in self.top_level_db_columns:
            report_column.format_data(ret)

        for computed_column in self.top_level_computed_columns:
            for row in ret:
                row[computed_column.column_id] = computed_column.wrapped_expression(row)

        return ret

    @method_decorator(catch_and_raise_exceptions)
    def get_total_records(self):
        qc = self.query_context()
        for c in self.columns:
            # TODO - don't append columns that are not part of filters or group bys
            qc.append_column(c.view)

        session = connection_manager.get_scoped_session(self.engine_id)
        return qc.count(session.connection(), self.filter_values)

    @method_decorator(catch_and_raise_exceptions)
    def get_total_row(self):
        def _clean_total_row(val, col):
            if isinstance(val, numbers.Number):
                return val
            elif col.calculate_total:
                return 0
            return ''

        def _get_relevant_column_ids(col, column_id_to_expanded_column_ids):
            return column_id_to_expanded_column_ids.get(col.column_id, [col.column_id])

        expanded_columns = get_expanded_columns(self.top_level_columns, self.config)

        qc = self.query_context()
        for c in self.columns:
            qc.append_column(c.view)

        session = connection_manager.get_scoped_session(self.engine_id)
        totals = qc.totals(
            session.connection(),
            [
                column_id
                for col in self.top_level_columns for column_id in _get_relevant_column_ids(col, expanded_columns)
                if col.calculate_total
            ],
            self.filter_values
        )

        total_row = [
            _clean_total_row(totals.get(column_id), col)
            for col in self.top_level_columns for column_id in _get_relevant_column_ids(
                col, expanded_columns
            )
        ]
        if total_row and total_row[0] is '':
            total_row[0] = ugettext('Total')
        return total_row
