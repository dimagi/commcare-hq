from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name

from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, transform_day_to_month


class AggLsDataHelper(BaseICDSAggregationHelper):
    """

    """
    base_tablename = 'agg_ls_report'
    awc_location_ucr = 'static-awc_location'
    ls_vhnd_ucr = 'static-ls_vhnd_form'
    ls_home_visit_ucr = 'static-ls_home_visit_forms_filled'
    ls_awc_mgt_ucr = 'static-awc_mgt_forms'

    def __init__(self, month):
        self.month_start = transform_day_to_month(month)

    def _tablename_func(self, agg_level):
        return "{}_{}_{}".format(self.base_tablename, self.month_start.strftime("%Y-%m-%d"), agg_level)

    def drop_table_if_exists(self, agg_level):
        return """
        DROP TABLE IS EXISTS "{table_name}"
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

        :return:
        """

        return """
        INSERT INTO "{tablename}"
        (state_id, district_id, block_id, supervisor_id, month,
         unique_awc_vists, vhnd_observed, beneficiary_vists, aggregation_level
        )
        (
        SELECT DISTINCT
        state_id,
        district_id,
        block_id,
        supervisor_id,
        %(start_date)s,
        0,
        0,
        0,
        4
        FROM "{awc_location_ucr}"
        )
        """.format(
            tablename = self.tablename,
            awc_location_ucr = self._ucr_tablename(ucr_id=self.awc_location_ucr)
        ), {
            'start_date': self.month_start
        }

    def updates(self):
        """

        :return:
        """

        yield """
            UPDATE "{tablename}" agg_ls_report
            SET vhnd_observed = ut.vhnd_observed
            FROM (
                SELECT count(*) as vhnd_observed,
                location_id as supervisor_id
                FROM "{ls_vhnd_ucr}"
                WHERE vhnd_date =  %(start_date)s
                GROUP BY location_id
            ) ut
            WHERE agg_ls_report.supervisor_id = ut.supervisor_id   
        """.format(
            tablename = self.tablename,
            ls_vhnd_ucr = self._ucr_tablename(ucr_id=self.ls_vhnd_ucr)
        ), {
            "start_date": self.month_start
        }

        yield """
            UPDATE "{tablename}" agg_ls_report
            SET unique_awc_vists = ut.unique_awc_vists
            FROM (
                SELECT count(distinct awc_id) as unique_awc_vists,
                location_id as supervisor_id
                FROM "{ls_home_visit_ucr}"
                WHERE submitted_on = %(start_date)s
                GROUP BY location_id
            ) ut
            WHERE agg_ls_report.supervisor_id = ut.supervisor_id
            AND visit_type is not null and visit_type <> ''
        """.format(
            tablename = self.tablename,
            ls_vhnd_ucr = self._ucr_tablename(ucr_id=self.ls_vhnd_ucr)
        ), {
            "start_date": self.month_start
        }

        yield """
            UPDATE "{tablename}" agg_ls_report
            SET unique_awc_vists = ut.unique_awc_vists
            FROM (
                SELECT
                count(distinct awc_id) as unique_awc_vists,
                location_id as supervisor_id
                FROM "{ls_awc_mgt_ucr}"
                WHERE submitted_on=%(start_date)s
                GROUP BY location_id
            ) ut
            WHERE 
              agg_ls_report.supervisor_id = ut.supervisor_id AND 
              location_entered is not null AND 
              location_entered <> ''
        """.format(
            tablename = self.tablename,
            ls_vhnd_ucr = self._ucr_tablename(ucr_id=self.ls_vhnd_ucr)
        ), {
            "start_date": self.month_start
        }

    def indexes(self, aggregation_level):
        indexes = []
        agg_locations = ['state_id']
        if aggregation_level > 1:
            indexes.append('CREATE INDEX ON "{}" (district_id)'.format(self.tablename))
            agg_locations.append('district_id')
        if aggregation_level > 2:
            indexes.append('CREATE INDEX ON "{}" (block_id)'.format(self.tablename))
            agg_locations.append('block_id')
        if aggregation_level > 3:
            indexes.append('CREATE INDEX ON "{}" (supervisor_id)'.format(self.tablename))
            agg_locations.append('supervisor_id')

        indexes.append('CREATE INDEX ON "{}" ({})'.format(self.tablename, ', '.join(agg_locations)))
        return indexes

    def rollup_query(self, agg_level):
        """

        :return:
        """

        locations = ['state_id', 'district_id', 'block_id','supervisor_id']

        for i in range(3, agg_level-1, -1):
            locations[i] = "'All'"

        return """
            INSERT INTO "{to_table}" agg_ls_report(
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
                agg_level,
                {locations},
                month,
                FROM "{from_table}"
                GROUP BY {group_by}, month
            )
        """.format(
            agg_level=agg_level,
            to_table=self._tablename_func(agg_level),
            locations=','.join(locations),
            from_table=self._tablename_func(agg_level+1),
            group_by=','.join(locations[:agg_level+1])
        )
