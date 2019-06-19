from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta
from six.moves import range

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import AGG_LS_VHND_TABLE, AGG_LS_AWC_VISIT_TABLE, AGG_LS_BENEFICIARY_TABLE
from custom.icds_reports.utils.aggregation_helpers import transform_day_to_month, month_formatter
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class AggLsHelper(BaseICDSAggregationHelper):
    helper_key = 'agg-ls'
    base_tablename = 'agg_ls'
    awc_location_ucr = 'static-awc_location'

    def __init__(self, month):
        self.month_start = transform_day_to_month(month)
        self.next_month_start = self.month_start + relativedelta(months=1)

    def aggregate(self, cursor):
        drop_table_queries = [self.drop_table_if_exists(i) for i in range(4, 0, -1)]
        create_table_queries = [self.create_child_table(i) for i in range(4, 0, -1)]

        agg_query, agg_params = self.aggregate_query()
        rollup_queries = [self.rollup_query(i) for i in range(3, 0, -1)]
        index_queries = [self.indexes(i) for i in range(4, 0, -1)]
        index_queries = [query for index_list in index_queries for query in index_list]

        for drop_table_query in drop_table_queries:
            cursor.execute(drop_table_query)
        for create_table_query, create_params in create_table_queries:
            cursor.execute(create_table_query, create_params)

        cursor.execute(agg_query, agg_params)

        for rollup_query in rollup_queries:
            cursor.execute(rollup_query)

        for index_query in index_queries:
            cursor.execute(index_query)

    def _tablename_func(self, agg_level):
        return "{}_{}_{}".format(self.base_tablename, self.month_start.strftime("%Y-%m-%d"), agg_level)

    def drop_table_if_exists(self, agg_level):
        return """
        DROP TABLE IF EXISTS "{table_name}"
        """.format(table_name=self._tablename_func(agg_level))

    def create_child_table(self, agg_level):
        return """
        CREATE TABLE "{table_name}" (
        CHECK (month=DATE %(start_date)s AND aggregation_level={agg_level})
        ) INHERITS ({base_tablename})
        """.format(
            table_name=self._tablename_func(agg_level),
            base_tablename=self.base_tablename,
            agg_level=agg_level
        ), {
            "start_date": self.month_start
        }

    @property
    def tablename(self):
        return self._tablename_func(4)

    def _ucr_tablename(self, ucr_id):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def aggregate_query(self):
        """
        Returns the base aggregate query which is used to insert all the locations
        into the LS data table.
        """

        columns = (
            ('state_id', 'location.state_id'),
            ('district_id', 'location.district_id'),
            ('block_id', 'location.block_id'),
            ('supervisor_id', 'location.supervisor_id'),
            ('month', "'{}'".format(month_formatter(self.month_start))),
            ('awc_visits', 'COALESCE(awc_table.awc_visits, 0)'),
            ('vhnd_observed', 'COALESCE(vhnd_table.vhnd_observed, 0)'),
            ('beneficiary_vists', 'COALESCE(beneficiary_table.beneficiary_vists, 0)'),
            ('aggregation_level', '4')
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        )
        (
        SELECT
        {calculations}
        from (select distinct state_id, district_id, block_id, supervisor_id from "{awc_location_ucr}" where (
        state_is_test=0 AND
        district_is_test=0 AND
        block_is_test=0 AND
        supervisor_is_test=0
        )) location
        LEFT  JOIN "{awc_table}" awc_table on (
            location.supervisor_id=awc_table.supervisor_id AND
            awc_table.month = %(start_date)s
        )
        LEFT  JOIN "{vhnd_table}" vhnd_table on (
            location.supervisor_id = vhnd_table.supervisor_id AND
            vhnd_table.month = %(start_date)s
        )
        LEFT  JOIN "{beneficiary_table}" beneficiary_table on (
            location.supervisor_id = beneficiary_table.supervisor_id AND
            beneficiary_table.month = %(start_date)s
        )
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            awc_location_ucr=self._ucr_tablename(ucr_id=self.awc_location_ucr),
            awc_table=AGG_LS_AWC_VISIT_TABLE,
            vhnd_table=AGG_LS_VHND_TABLE,
            beneficiary_table=AGG_LS_BENEFICIARY_TABLE
        ), {
            'start_date': self.month_start
        }

    def indexes(self, aggregation_level):
        """
        Returns queries to create indices  for columns
        district_id, block_id, supervisor_id and state_id based on
        aggregation level
        """
        indexes = []
        agg_locations = ['state_id']
        if aggregation_level > 1:
            indexes.append('CREATE INDEX ON "{}" (district_id)'.format(self._tablename_func(aggregation_level)))
            agg_locations.append('district_id')
        if aggregation_level > 2:
            indexes.append('CREATE INDEX ON "{}" (block_id)'.format(self._tablename_func(aggregation_level)))
            agg_locations.append('block_id')
        if aggregation_level > 3:
            indexes.append('CREATE INDEX ON "{}" (supervisor_id)'.format(self._tablename_func(aggregation_level)))
            agg_locations.append('supervisor_id')

        indexes.append('CREATE INDEX ON "{}" ({})'.format(self._tablename_func(aggregation_level),
                                                          ', '.join(agg_locations)))
        return indexes

    def rollup_query(self, agg_level):
        """
        Returns the roll up query to the agg_level passed as argument.
        Roll up query is used to roll up the data from supervisor level
        to block level to district level to state level
        """
        locations = ['state_id', 'district_id', 'block_id', 'supervisor_id']

        for i in range(3, agg_level - 1, -1):
            locations[i] = "'All'"

        return """
            INSERT INTO "{to_table}" (
            vhnd_observed,
            beneficiary_vists,
            awc_visits,
            aggregation_level,
            state_id,
            district_id,
            block_id,
            supervisor_id,
            month)
            (
                SELECT
                sum(vhnd_observed) as vhnd_observed,
                sum(beneficiary_vists) as beneficiary_vists,
                sum(awc_visits) as awc_visits,
                {agg_level},
                {locations},
                month
                FROM "{from_table}"
                GROUP BY {group_by}, month
            )
        """.format(
            agg_level=agg_level,
            to_table=self._tablename_func(agg_level),
            locations=','.join(locations),
            from_table=self._tablename_func(agg_level + 1),
            group_by=','.join(locations[:agg_level])
        )
