from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_THR_V2_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class THRFormV2AggDistributedHelper(BaseICDSAggregationHelper):
    helper_key = 'thr-form-v2'
    ucr_data_source_id = 'static-thr_forms_v2'
    aggregate_parent_table = AGG_THR_V2_TABLE
    aggregate_child_table_prefix = 'icds_db_thr_form_v2_'

    def aggregate(self, cursor):
        drop_query = self.drop_table_query()
        curr_month_query, curr_month_params = self.create_table_query()
        agg_query, agg_param = self.aggregate_query()
        cursor.execute(drop_query)
        cursor.execute(curr_month_query, curr_month_params)
        cursor.execute(agg_query, agg_param)

    def aggregate_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)
        next_month_start = self.month + relativedelta(months=1)

        query_params = {
            "state_id": self.state_id,
            "start_date": month_formatter(month),
            "end_date": month_formatter(next_month_start)
        }

        return """
        INSERT INTO "{tablename}" (
        state_id, supervisor_id, awc_id, thr_distribution_image_count, month
        ) (
            SELECT
                state_id,
                supervisor_id,
                awc_id,
                COUNT(*) FILTER (WHERE photo_thr_packets_distributed is not null) as thr_distribution_image_count,
                %(start_date)s::DATE AS month
                FROM "{ucr_tablename}"
                WHERE submitted_on >= %(start_date)s AND submitted_on < %(end_date)s
                    AND state_id=%(state_id)s
                GROUP BY state_id, supervisor_id, awc_id
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename
        ), query_params
