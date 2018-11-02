from __future__ import absolute_import
from __future__ import unicode_literals

from custom.icds_reports.const import AWW_INCENTIVE_TABLE
from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, month_formatter


class AwwIncentiveAggregationHelper(BaseICDSAggregationHelper):
    aggregate_parent_table = AWW_INCENTIVE_TABLE
    aggregate_child_table_prefix = 'icds_db_aww_incentive_'

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)

        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id
        }

        return """
        INSERT INTO "{tablename}" (
            state_id, month, awc_id, block_id, state_name, district_name, block_name, 
            supervisor_name, awc_name, aww_name, contact_phone_number, wer_weighed,
            wer_eligible, awc_num_open, valid_visits, expected_visits
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            awc_id,
            block_id,
            state_name,
            district_name,
            block_name,
            supervisor_name,
            awc_name,
            aww_name,
            contact_phone_number,
            wer_weighed,
            wer_eligible,
            awc_num_open,
            valid_visits,
            expected_visits
          FROM agg_ccs_record_monthly AS acm
          WHERE acm.month = %(month)s AND acm.state_id = %(state_id)s and aggregation_level=5
        )
        """.format(
            tablename=tablename
        ), query_params
