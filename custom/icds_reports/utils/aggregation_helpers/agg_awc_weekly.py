from __future__ import absolute_import
from __future__ import unicode_literals
from dateutil.relativedelta import relativedelta

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import USAGE_TABLE_ID

from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, date_to_string


class AggAwcWeeklyAggregationHelper(BaseICDSAggregationHelper):
    base_tablename = 'agg_awc'
    usage_table = USAGE_TABLE_ID

    def __init__(self, month):
        self.month = month

    @property
    def usage_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.usage_table)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def aggregate_query(self):
        month_start_6m = self.month - relativedelta(month=6)

        return """
           UPDATE "{tablename}" SET
            usage_num_hh_reg = ut.usage_num_hh_reg,
            is_launched = ut.is_launched,
            num_launched_states = ut.num_launched_awcs,
            num_launched_districts = ut.num_launched_awcs,
            num_launched_blocks = ut.num_launched_awcs,
            num_launched_supervisors = ut.num_launched_awcs,
            num_launched_awcs = ut.num_launched_awcs,
            usage_awc_num_active = ut.usage_awc_num_active
          FROM (SELECT
            awc_id,
            month,
            sum(add_household) AS usage_num_hh_reg,
            CASE WHEN sum(add_household) > 0 THEN 'yes' ELSE 'no' END as is_launched,
            CASE WHEN sum(add_household) > 0 THEN 1 ELSE 0 END as num_launched_awcs,
            CASE WHEN (
              sum(due_list_ccs) +
              sum(due_list_child) +
              sum(pse) +
              sum(gmp) +
              sum(thr) +
              sum(home_visit) +
              sum(add_pregnancy) +
              sum(add_household)
            ) >= 15 THEN 1 
            ELSE 0 END AS usage_awc_num_active
            FROM "{usage_tablename}"
            WHERE month >= %(month_start_6m)s GROUP BY awc_id, month) ut
          WHERE ut.month <= agg_awc.month AND ut.awc_id = agg_awc.awc_id AND aggregation_level=5
          AND agg_awc.num_launched_awcs = 0 AND ut.num_launched_awcs != 0
        """.format(
            tablename=self.base_tablename,
            usage_tablename=self.usage_tablename
        ), {
            "month_start_6m": date_to_string(month_start_6m)
        }

    def rollup_query(self, aggregation_level):
        month_start_6m = self.month - relativedelta(month=6)

        group_by = ["state_id"]
        location_column = 'state_id'
        if aggregation_level > 1:
            group_by.append("district_id")
            location_column = 'district_id'
        if aggregation_level > 2:
            group_by.append("block_id")
            location_column = 'block_id'
        if aggregation_level > 3:
            group_by.append("supervisor_id")
            location_column = 'supervisor_id'

        group_by.append("month")

        return """
          UPDATE "{tablename}" SET
            usage_num_hh_reg = ut.sum_usage_num_hh_reg,
            num_launched_states = ut.num_launched_supervisors,
            num_launched_districts = ut.num_launched_supervisors,
            num_launched_blocks = ut.num_launched_supervisors,
            num_launched_supervisors = ut.num_launched_supervisors,
            num_launched_awcs = ut.sum_num_launched_awcs,
            usage_awc_num_active = ut.usage_awc_num_active
          FROM (SELECT
            {location_column},
            month,
            sum(usage_num_hh_reg) as sum_usage_num_hh_reg,
            CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END as num_launched_supervisors,
            sum(num_launched_awcs) as sum_num_launched_awcs,
            sum(usage_awc_num_active) as usage_awc_num_active
            FROM "{tablename}"
            WHERE aggregation_level=%(child_aggregation_level)s AND month >= %(month_start_6m)s
            GROUP BY {group_by}) ut
          WHERE ut.month = agg_awc.month AND ut.{location_column} = agg_awc.{location_column} 
            AND aggregation_level=%(aggregation_level)s
        """.format(
            tablename=self.base_tablename,
            group_by=", ".join(group_by),
            location_column=location_column
        ), {
            "month_start_6m": month_start_6m,
            "aggregation_level": aggregation_level,
            "child_aggregation_level": aggregation_level + 1
        }