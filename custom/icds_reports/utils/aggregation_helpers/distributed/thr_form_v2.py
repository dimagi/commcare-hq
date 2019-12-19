from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_THR_V2_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationDistributedHelper,
)


class THRFormV2AggDistributedHelper(StateBasedAggregationDistributedHelper):
    helper_key = 'thr-form-v2'
    ucr_data_source_id = 'static-thr_forms_v2'
    aggregate_parent_table = AGG_THR_V2_TABLE
    months_required = 0

    def aggregation_query(self):
        month = self.month.replace(day=1)
        next_month_start = self.month + relativedelta(months=1)

        query_params = {
            "state_id": self.state_id,
            "start_date": month_formatter(month),
            "end_date": month_formatter(next_month_start)
        }

        return """
        DROP TABLE IF EXISTS "temp_thr";
        CREATE TEMPORARY TABLE "temp_thr" AS
            SELECT
                state_id,
                supervisor_id,
                awc_id,
                COUNT(*) FILTER (WHERE NULLIF(photo_thr_packets_distributed,'') is not null) as thr_distribution_image_count,
                %(start_date)s::DATE AS month
                FROM "{ucr_tablename}"
                WHERE submitted_on >= %(start_date)s AND submitted_on < %(end_date)s
                    AND state_id=%(state_id)s
                GROUP BY state_id, supervisor_id, awc_id;
        INSERT INTO "{tablename}" (
            state_id, supervisor_id, awc_id, thr_distribution_image_count, month
        )
        SELECT * from "temp_thr";
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table
        ), query_params
