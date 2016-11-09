from collections import OrderedDict

from django.utils.decorators import method_decorator

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.es.aggregations import SumAggregation, TermsAggregation
from corehq.apps.es.es_query import HQESQuery

from corehq.apps.userreports.columns import get_expanded_column_config
from corehq.apps.userreports.decorators import catch_and_raise_exceptions
from corehq.apps.userreports.models import DataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.sql.data_source import ConfigurableReportSqlDataSource
from corehq.apps.userreports.reports.sorting import ASCENDING, DESCENDING
from corehq.apps.userreports.util import get_table_name


class ConfigurableReportEsDataSource(ConfigurableReportSqlDataSource):
    @property
    def config(self):
        if self._config is None:
            self._config, _ = get_datasource_config(self._config_id, self.domain)
        return self._config

    @property
    def table_name(self):
        # TODO make this the same function as the adapter
        return super(ConfigurableReportEsDataSource, self).table_name.lower()

    @property
    def filters(self):
        return filter(None, [f.to_es_filter() for f in self._filter_values.values()])

    @property
    def order_by(self):
        if self._order_by:
            return [
                (col.field, order)
                for sort_column_id, order in self._order_by
                for col in [self._column_configs[sort_column_id]]
            ]
        elif self.top_level_columns:
            col = self.top_level_columns[0]
            return [(col.field, ASCENDING)]
        return []

    @property
    def columns(self):
        db_columns = [c for conf in self.column_configs for c in conf.columns]
        return db_columns

    @property
    def column_configs(self):
        return [col.get_column_config(self.config, self.lang) for col in self.top_level_columns]

    @property
    def column_warnings(self):
        return [w for conf in self.column_configs for w in conf.warnings]

    @property
    @memoized
    def uses_aggregations(self):
        return not(len(self.aggregation_columns) == 1 and self.aggregation_columns[0] == 'doc_id')

    @memoized
    @method_decorator(catch_and_raise_exceptions)
    def get_data(self, start=None, limit=None):
        if self.uses_aggregations:
            ret = self._get_aggregated_results(start, limit)
        else:
            ret = self._get_query_results(start, limit)

        for report_column in self.top_level_db_columns:
            report_column.format_data(ret)

        for computed_column in self.top_level_computed_columns:
            for row in ret:
                row[computed_column.column_id] = computed_column.wrapped_expression(row)

        return ret

    @memoized
    def _get_query_results(self, start, limit):
        hits = self._get_query(start, limit).hits
        ret = []

        for row in hits:
            r = {}
            for report_column in self.top_level_db_columns:
                if report_column.type == 'expanded':
                    # todo aggregation only supports # of docs matching
                    counter = 0
                    for sub_col in get_expanded_column_config(self.config, report_column, 'en').columns:
                        ui_col = report_column.column_id + "-" + str(counter)
                        # todo move interpretation of data into column config
                        if row[report_column.column_id] == sub_col.expand_value:
                            r[ui_col] = 1
                        else:
                            r[ui_col] = 0
                        counter += 1
                else:
                    r[report_column.column_id] = row[report_column.field]
            ret.append(r)

        return ret

    @memoized
    def _get_query(self, start=None, limit=None):
        query = HQESQuery(self.table_name).source(self.required_fields)
        for column, order in self.order_by:
            query = query.sort(column, desc=(order == DESCENDING), reset_sort=False)

        if start:
            query = query.start(start)
        if limit:
            query = query.size(limit)

        for filter in self.filters:
            query = query.filter(filter)

        return query.run()

    @memoized
    def _get_aggregated_results(self, start, limit):
        query = self._get_aggregated_query(start, limit)
        hits = getattr(query.aggregations, self.aggregation_columns[0]).raw
        hits = hits[self.aggregation_columns[0]]['buckets'][start:]
        ret = []

        for row in hits:
            r = {}
            for report_column in self.top_level_columns:
                if report_column.type == 'expanded':
                    # todo aggregation only supports # of docs matching
                    for sub_col in get_expanded_column_config(self.config, report_column, 'en').columns:
                        # todo move interpretation of data into column config
                        r[sub_col.ui_alias] = row[sub_col.es_alias]['doc_count']
                elif report_column.field == self.aggregation_columns[0]:
                    r[report_column.column_id] = row['key']
                elif report_column.aggregation == 'sum':
                    r[report_column.column_id] = int(row[report_column.field]['value'])
                else:
                    r[report_column.column_id] = row[report_column.field]['doc_count']
            ret.append(r)

        return ret

    @memoized
    def _get_aggregated_query(self, start, limit):
        max_size = (start or 0) + (limit or 0)
        query = HQESQuery(self.table_name).size(0)
        for filter in self.filters:
            query = query.filter(filter)

        top_agg = TermsAggregation(self.aggregation_columns[0], self.aggregation_columns[0], size=max_size)
        for agg_column in self.aggregation_columns[1:]:
            # todo support multiple aggregations
            pass

        aggregations = []
        for col in self.top_level_columns:
            if col.type == 'expanded':
                for sub_col in get_expanded_column_config(self.config, col, 'en').columns:
                    aggregations.append(sub_col.aggregation)
            elif col.type == 'field':
                if col.aggregation == 'sum':
                    # todo push this to the column
                    aggregations.append(SumAggregation(col.field, col.field))

        for agg in aggregations:
            top_agg = top_agg.aggregation(agg)

        if self.order_by:
            # todo sort by more than one column
            # todo sort by by something other than the first aggregate column
            col, desc = self.order_by[0]
            if col == self.aggregation_columns[0] or col == self.top_level_columns[0].field:
                top_agg = top_agg.order('_count', desc)

        query = query.aggregation(top_agg)

        return query.run()

    @method_decorator(catch_and_raise_exceptions)
    def get_total_records(self):
        if self.uses_aggregations:
            # this can probably be done better with cardinality aggregation
            query = self._get_aggregated_query(0, 0)
            hits = getattr(query.aggregations, self.aggregation_columns[0]).raw
            return len(hits[self.aggregation_columns[0]]['buckets'])

        return self._get_query().total

    @property
    def required_fields(self):
        ret = [c.field for c in self.top_level_db_columns]
        return ret + [c for c in self.aggregation_columns]

    @method_decorator(catch_and_raise_exceptions)
    def get_total_row(self):
        # todo calculate total row
        return []

    # sql only methods that should never be called
    @property
    def engine_id(self):
        raise NotImplementedError

    def set_filter_values(self, filter_values):
        # this does nothing here. it's only used in sql, but can't throw error yet
        pass

    @property
    def keys(self):
        raise NotImplementedError

    @property
    def wrapped_filters(self):
        raise NotImplementedError

    def query_context(self, start=None, limit=None):
        raise NotImplementedError
