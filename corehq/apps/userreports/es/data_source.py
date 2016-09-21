from collections import OrderedDict

from django.utils.decorators import method_decorator

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.es.aggregations import TermsAggregation
from corehq.apps.es.es_query import HQESQuery

from corehq.apps.reports.api import ReportDataSource
from corehq.apps.userreports.decorators import catch_and_raise_exceptions
from corehq.apps.userreports.es.columns import get_expanded_es_column_config
from corehq.apps.userreports.models import DataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.reports.sorting import ASCENDING, DESCENDING
from corehq.apps.userreports.util import get_table_name


class ConfigurableReportEsDataSource(ReportDataSource):
    def __init__(self, domain, config_or_config_id, filters, aggregation_columns, columns, order_by):
        self.lang = None
        self.domain = domain
        if isinstance(config_or_config_id, DataSourceConfiguration):
            self._config = config_or_config_id
            self._config_id = self._config._id
        else:
            assert isinstance(config_or_config_id, basestring)
            self._config = None
            self._config_id = config_or_config_id

        self._filters = {f.slug: f for f in filters}
        self._filter_values = {}
        self._deferred_filters = {}
        self._order_by = order_by
        self._aggregation_columns = aggregation_columns
        self._column_configs = OrderedDict()
        for column in columns:
            # should be caught in validation prior to reaching this
            assert column.column_id not in self._column_configs, \
                'Report {} in domain {} has more than one {} column defined!'.format(
                    self._config_id, self.domain, column.column_id,
                )
            self._column_configs[column.column_id] = column

    @property
    def aggregation_columns(self):
        # TODO add deferred filters to support mobile ucr
        return self._aggregation_columns

    @property
    def config(self):
        if self._config is None:
            self._config, _ = get_datasource_config(self._config_id, self.domain)
        return self._config

    @property
    def column_configs(self):
        return self._column_configs.values()

    @property
    def table_name(self):
        # TODO make this the same function as the adapter
        return get_table_name(self.domain, self.config.table_id).lower()

    @property
    def filters(self):
        return filter(None, [f.to_es_filter() for f in self._filter_values.values()])

    def set_filter_values(self, filter_values):
        for filter_slug, value in filter_values.items():
            self._filter_values[filter_slug] = self._filters[filter_slug].create_filter_value(value)

    def defer_filters(self, filter_slugs):
        self._deferred_filters.update({
            filter_slug: self._filters[filter_slug] for filter_slug in filter_slugs})

    def set_order_by(self, columns):
        self._order_by = columns

    @property
    def order_by(self):
        if self._order_by:
            return [
                (col.field, order)
                for sort_column_id, order in self._order_by
                for col in [self._column_configs[sort_column_id]]
            ]
        elif self.column_configs:
            col = self.column_configs[0]
            return [(col.field, ASCENDING)]
        return []

    @property
    def columns(self):
        db_columns = [c for sql_conf in self.es_column_configs for c in sql_conf.columns]
        return db_columns

    @property
    def es_column_configs(self):
        return [col.get_es_column_config(self.config, self.lang) for col in self.column_configs]

    @property
    def column_warnings(self):
        return [w for es_conf in self.es_column_configs for w in es_conf.warnings]

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

        for report_column in self.column_configs:
            report_column.format_data(ret)

        return ret

    @memoized
    def _get_query_results(self, start, limit):
        hits = self._get_query(start, limit).hits
        ret = []

        for row in hits:
            r = {}
            for report_column in self.column_configs:
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
        hits = hits[self.aggregation_columns[0]]['buckets']
        ret = []

        for row in hits:
            r = {}
            for report_column in self.column_configs:
                if report_column.type == 'expanded':
                    # todo aggregation only supports # of docs matching
                    for sub_col in get_expanded_es_column_config(self.config, report_column, 'en').columns:
                        # todo move interpretation of data into column config
                        r[sub_col.ui_alias] = row[sub_col.es_alias]['doc_count']
                elif report_column.field == self.aggregation_columns[0]:
                    r[report_column.column_id] = row['key']
                else:
                    r[report_column.column_id] = row[report_column.field]['doc_count']
            ret.append(r)

        return ret

    @memoized
    def _get_aggregated_query(self, start, limit):
        # todo support sorting and sizing
        query = HQESQuery(self.table_name).size(0)
        for filter in self.filters:
            query = query.filter(filter)

        top_agg = TermsAggregation(self.aggregation_columns[0], self.aggregation_columns[0])
        for agg_column in self.aggregation_columns[1:]:
            # todo support multiple aggregations
            pass

        aggregations = []
        for col in self.column_configs:
            if col.type != 'expanded':
                continue

            for sub_col in get_expanded_es_column_config(self.config, col, 'en').columns:
                aggregations.append(sub_col.aggregation)

        for agg in aggregations:
            top_agg = top_agg.aggregation(agg)

        query = query.aggregation(top_agg)

        return query.run()

    @property
    def has_total_row(self):
        return any(column_config.calculate_total for column_config in self.column_configs)

    @method_decorator(catch_and_raise_exceptions)
    def get_total_records(self):
        return self._get_query().total

    @property
    def required_fields(self):
        ret = [c.field for c in self.column_configs]
        return ret + [c for c in self.aggregation_columns]

    @method_decorator(catch_and_raise_exceptions)
    def get_total_row(self):
        return []
