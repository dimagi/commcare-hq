from collections import OrderedDict

import sqlagg
from sqlalchemy import select
from sqlalchemy.sql import func

from corehq.apps.userreports.custom.data_source import (
    ConfigurableReportCustomQueryProvider,
)


class TwoStageAggregateCustomQueryProvider(ConfigurableReportCustomQueryProvider):
    """
    Reasons this is needed:
      - Filter column based on a SQL aggregate / case function

    This is a completely generic class that should work with any UCR report that needs to do
    filters based off an aggregate query (e.g. a sum_when column).

    Any column listed in AGGREGATE_FILTERS will be filtered in an outer query with the main
    query running in a subquery first.
    """
    # these filters will be applied in the outer query
    AGGREGATE_FILTERS = []

    def __init__(self, report_data_source):
        self.report_data_source = report_data_source
        self.helper = self.report_data_source.helper
        self.table = self.helper.get_table()

    def _split_filters(self, filters):
        """
        Returns a data structure of filters split for the inner query and the outer query
        based on self.AGGREGATE_FILTERS
        :param filters: The complete list of filters
        :param filter_values: The complete list of filter_values
        :return: {
           "inner": [ list of inner filters ],
           "outer": [ list of outer filters ],
        }
        """
        # specifying ancestor_location returns an ANDFilter and does not have a column name
        # assume that it should go into inner filters
        complex_filters = [f for f in filters if not hasattr(f, 'column_name')]
        simple_filters = [f for f in filters if hasattr(f, 'column_name')]
        inner_filters = [f for f in simple_filters if f.column_name not in self.AGGREGATE_FILTERS]
        outer_filters = [f for f in simple_filters if f.column_name in self.AGGREGATE_FILTERS]
        return {
            'inner': inner_filters + complex_filters,
            'outer': outer_filters,
        }

    def _get_select_query(self):
        # break filters into those that can be used in the inner query and those that
        # need to bubble up to the outer query (aggregates)
        split_filters = self._split_filters(self.helper._filters)
        # a lot of what follows is copy/modified from SqlData._get_data() and corresponding call chain
        # e.g. SimpleQueryMeta._build_query_generic in sqlagg
        query_context = sqlagg.QueryContext(
            self.table.name,
            filters=split_filters['inner'],
            group_by=self.report_data_source.group_by,
            # note: is this necessary to add?
            # order_by=self.order_by,
        )
        for c in self.report_data_source.columns:
            query_context.append_column(c.view)

        if len(query_context.query_meta.values()) > 1:
            raise Exception('Use of this class assumes only one query meta value!')

        query_meta = list(query_context.query_meta.values())[0]
        # note: sqlagg doesn't expose access to sqlalchemy except through this private method
        query = query_meta._build_query()
        if split_filters['outer']:
            # if there are outer filters we have to do a two-stage query
            # first add a subquery (with alias)
            query = query.alias().select()
            for f in split_filters['outer']:
                # then apply outer filters to the subquery
                query.append_whereclause(f.build_expression())

        return query

    def get_data(self, start=None, limit=None):
        select_query = self._get_select_query()
        if start is not None:
            select_query = select_query.offset(start)
        if limit is not None:
            select_query = select_query.limit(limit)

        with self.helper.session_helper().session_context() as session:
            results = session.connection().execute(
                select_query,
                **self.helper.sql_alchemy_filter_values
            ).fetchall()

        def _extract_aggregate_key(row):
            return tuple(getattr(row, key_component) for key_component in self.report_data_source.group_by)

        def _row_proxy_to_dict(row):
            return dict(row.items())  # noqa: RowProxy doesn't support iteritems

        return OrderedDict([
            (_extract_aggregate_key(row), _row_proxy_to_dict(row)) for row in results
        ])

    def get_total_row(self):
        raise NotImplementedError("This data source doesn't support total rows")

    def get_total_records(self):
        select_query = self._get_select_query()
        with self.helper.session_helper().session_context() as session:
            count_query = select([func.count()]).select_from(select_query.alias())
            return session.connection().execute(count_query, **self.helper.sql_alchemy_filter_values).scalar()


class MPR2BIPregDeliveryDeathList(TwoStageAggregateCustomQueryProvider):
    AGGREGATE_FILTERS = ['dead_preg_count']
