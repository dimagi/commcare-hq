from __future__ import absolute_import
from collections import OrderedDict
import copy
from six.moves import filter as ifilter

from django.utils.decorators import method_decorator
from django.utils.translation import ugettext

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.es.aggregations import MinAggregation, SumAggregation, TermsAggregation
from corehq.apps.es.es_query import HQESQuery

from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.sqlreport import DataFormatter, DictDataFormat
from corehq.apps.userreports.decorators import catch_and_raise_exceptions
from corehq.apps.userreports.es.columns import safe_es_column
from corehq.apps.userreports.exceptions import UserReportsError
from corehq.apps.userreports.mixins import ConfigurableReportDataSourceMixin
from corehq.apps.userreports.reports.sorting import ASCENDING, DESCENDING
from corehq.apps.userreports.reports.util import get_expanded_columns


class ConfigurableReportEsDataSource(ConfigurableReportDataSourceMixin, ReportDataSource):
    @property
    def table_name(self):
        # TODO make this the same function as the adapter
        return super(ConfigurableReportEsDataSource, self).table_name.lower()

    @property
    def filters(self):
        return list(ifilter(None, [f.to_es_filter() for f in self._filter_values.values()]))

    @property
    def order_by(self):
        ret = []
        if self._order_by:
            for sort_column_id, order in self._order_by:
                if sort_column_id in self._column_configs:
                    for col in [self._column_configs[sort_column_id]]:
                        ret.append((col.field, order))
                else:
                    ret.append((sort_column_id, order))
        elif self.top_level_columns:
            # can only sort by columns that come from the DB
            col = list(ifilter(lambda col: hasattr(col, 'field'), self.top_level_columns))
            if col:
                col = col[0]
                ret.append((col.field, ASCENDING))
        return ret

    @property
    def columns(self):
        db_columns = [c for conf in self.column_configs for c in conf.columns]
        return db_columns

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

        formatter = DataFormatter(DictDataFormat(self.columns, no_value=None))
        formatted_data = list(formatter.format(ret, group_by=self.group_by).values())

        for report_column in self.top_level_db_columns:
            report_column.format_data(formatted_data)

        for computed_column in self.top_level_computed_columns:
            for row in formatted_data:
                row[computed_column.column_id] = computed_column.wrapped_expression(row)

        return formatted_data

    @memoized
    def _get_query_results(self, start, limit):
        hits = self._get_query(start, limit).hits
        ret = OrderedDict()

        for row in hits:
            r = {}
            for report_column in self.top_level_db_columns:
                r.update(report_column.get_es_data(row, self.config, self.lang, from_aggregation=False))
            ret[row['doc_id']] = r

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
        def _parse_bucket(bucket, remaining_agg_columns, current_bucket_name, past_bucket_info):
            current_bucket_key = bucket['key']
            past_bucket_info.update({current_bucket_name: current_bucket_key})
            if remaining_agg_columns:
                sub_buckets = bucket[remaining_agg_columns[0]]['buckets']
                return _parse_buckets(
                    sub_buckets,
                    remaining_agg_columns[1:],
                    remaining_agg_columns[0],
                    past_bucket_info
                )

            ret = bucket
            ret['past_bucket_values'] = copy.deepcopy(past_bucket_info)
            return [ret]

        def _parse_buckets(buckets, remaining_agg_columns, current_bucket_name, past_bucket_info=None):
            past_bucket_info = past_bucket_info or {}

            ret = []
            for bucket in buckets:
                ret += _parse_bucket(bucket, remaining_agg_columns, current_bucket_name, past_bucket_info)
            return ret

        query = self._get_aggregated_query(start, limit)
        aggs = getattr(query.aggregations, self.aggregation_columns[0]).raw
        top_buckets = aggs[self.aggregation_columns[0]]['buckets']
        hits = _parse_buckets(top_buckets, self.aggregation_columns[1:], self.aggregation_columns[0])

        ret = OrderedDict()
        start = start or 0
        end = start + (limit or len(hits))
        relevant_hits = hits[start:end]

        for row in relevant_hits:
            r_ = {}
            for report_column in self.top_level_columns:
                r_.update(report_column.get_es_data(row, self.config, self.lang))

            key = []
            for col in self.group_by:
                if col in row['past_bucket_values']:
                    key.append(row['past_bucket_values'][col])
                else:
                    key.append(row[col])

            ret[tuple(key)] = r_

        return ret

    @memoized
    def _get_aggregated_query(self, start, limit):
        max_size = (start or 0) + (limit or 0)
        query = HQESQuery(self.table_name).size(0)
        for filter in self.filters:
            query = query.filter(filter)

        innermost_agg_col = self.aggregation_columns[-1]
        innermost_agg = TermsAggregation(innermost_agg_col, innermost_agg_col, size=max_size)

        aggregations = []
        for col in self.top_level_columns:
            for agg in col.aggregations(self.config, self.lang):
                innermost_agg.aggregation(agg)

        top_agg = innermost_agg
        # go through aggregations in reverse order so that they are nested properly
        for agg_column in self.aggregation_columns[:-1][::-1]:
            top_agg = TermsAggregation(agg_column, agg_column, size=max_size).aggregation(top_agg)

        if self.order_by:
            col, desc = self.order_by[0]
            valid_columns = (
                self.aggregation_columns[0],
                self.top_level_columns[0].field,
                self.top_level_columns[0].column_id
            )
            if col in valid_columns:
                top_agg = top_agg.order('_term', desc)

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
        ret = [field for c in self.top_level_db_columns
               for field in c.get_fields(self.config, self.lang)]
        return ret + [c for c in self.aggregation_columns]

    def _get_total_aggregated_results(self):
        query = HQESQuery(self.table_name).size(0)
        for filter in self.filters:
            query = query.filter(filter)

        columns = [col for col in self.top_level_columns if col.calculate_total]
        totals_aggregations = []

        for col in columns:
            for agg in col.aggregations(self.config, self.lang):
                totals_aggregations.append(agg)

        query = query.aggregations(totals_aggregations)

        return query.run().aggregations

    @method_decorator(catch_and_raise_exceptions)
    def get_total_row(self):
        def _clean_total_row(aggregations, aggregation_name):
            agg = getattr(aggregations, aggregation_name)
            if hasattr(agg, 'value'):
                return agg.value
            elif hasattr(agg, 'doc_count'):
                return agg.doc_count
            else:
                return ''

        def _get_relevant_column_ids(col):
            col_id_to_expanded_col = get_expanded_columns(self.top_level_columns, self.config)
            return col_id_to_expanded_col.get(col.column_id, [col.column_id])

        aggregations = self._get_total_aggregated_results()

        total_row = []
        for col in self.top_level_columns:
            for col_id in _get_relevant_column_ids(col):
                if not col.calculate_total:
                    total_row.append('')
                    continue
                elif getattr(col, 'aggregation', '') == 'simple':
                    # could have this append '', but doing this for
                    # compatibility with SQL
                    raise UserReportsError(ugettext("You cannot calculate the total of a simple column"))

                total_row.append(_clean_total_row(aggregations, safe_es_column(col_id)))

        if total_row and total_row[0] is '':
            total_row[0] = ugettext('Total')
        return total_row
