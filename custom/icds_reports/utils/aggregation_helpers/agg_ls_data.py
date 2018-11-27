from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta
from custom.icds_reports.const import AGG_LS_VHND_TABLE, AGG_LS_AWC_VISIT_TABLE, AGG_LS_BENEFICIARY_TABLE
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name

from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, transform_day_to_month


class AggLsHelper(BaseICDSAggregationHelper):

    base_tablename = 'agg_ls'
    awc_location_ucr = 'static-awc_location'
    ls_vhnd_ucr = 'static-ls_vhnd_form'
    ls_home_visit_ucr = 'static-ls_home_visit_forms_filled'
    ls_awc_mgt_ucr = 'static-awc_mgt_forms'

    def __init__(self, month):
        self.month_start = transform_day_to_month(month)
        self.next_month_start = self.month_start + relativedelta(months=1)

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
            ('supervisor_id', 'location.supervisor_id')
            ('month', self.month_start),
            ('unique_awc_vists', 'sum(awc_table.unique_awc_vists)'),
            ('vhnd_observed', 'sum(vhnd_table.vhnd_observed)'),
            ('beneficiary_vists', 'sum(beneficiary_table.beneficiary_vists)'),
            ('aggregation_level', '5')
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        )
        (
        SELECT
        {calculations}
        from "{awc_location_ucr}" location
        LEFT OUTER JOIN "{awc_table}" awc_table on location.supervisor_id=awc_table.supervisor_id
        LEFT OUTER JOIN "{vhnd_table}" vhnd_table on (
            awc_table.supervisor_id = vhnd_table.supervisor_id AND
            awc_table.month = vhnd_table.month
        )
        LEFT OUTER JOIN "{beneficiary_table}" beneficiary_table on (
        vhnd_table.supervisor_id = beneficiary_table.supervisor_id AND
        vhnd_table.month = beneficiary_table.month
        )
        WHERE ucr.month = %(start_date)s
        GROUP BY location.state_id, location.district_id, location.block_id, location.supervisor_id
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
            unique_awc_vists,
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
                sum(unique_awc_vists) as unique_awc_vists,
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
