from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_CHILD_HEALTH_THR_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationDistributedHelper,
)


class THRFormsChildHealthAggregationDistributedHelper(StateBasedAggregationDistributedHelper):
    helper_key = 'thr-forms-child-health'
    ucr_data_source_id = 'static-dashboard_thr_forms'
    aggregate_parent_table = AGG_CHILD_HEALTH_THR_TABLE
    months_required = 0

    def aggregation_query(self):
        month = self.month.replace(day=1)
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id,
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
        }

        return """
        INSERT INTO "{tablename}" (
          state_id, supervisor_id, month, case_id, latest_time_end_processed, days_ration_given_child
        ) (
          SELECT DISTINCT ON (child_health_case_id)
            %(state_id)s AS state_id,
            LAST_VALUE(supervisor_id) over w AS supervisor_id,
            %(month)s AS month,
            child_health_case_id AS case_id,
            MAX(timeend) over w AS latest_time_end_processed,
            CASE WHEN SUM(days_ration_given_child) over w < 32767 THEN SUM(days_ration_given_child) over w ELSE 32767 END AS days_ration_given_child
          FROM "{ucr_tablename}"
          WHERE state_id = %(state_id)s AND
                timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND
                child_health_case_id IS NOT NULL
          WINDOW w AS (PARTITION BY supervisor_id, child_health_case_id)
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table
        ), query_params
