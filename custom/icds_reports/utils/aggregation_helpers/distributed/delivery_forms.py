from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_CCS_RECORD_DELIVERY_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationDistributedHelper,
)


class DeliveryFormsAggregationDistributedHelper(StateBasedAggregationDistributedHelper):
    helper_key = 'delivery-forms'
    ucr_data_source_id = 'static-dashboard_delivery_forms'
    aggregate_parent_table = AGG_CCS_RECORD_DELIVERY_TABLE

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
          case_id, state_id, supervisor_id, month, latest_time_end_processed,
          breastfed_at_birth, valid_visits, where_born
        ) (
          SELECT
            DISTINCT case_load_ccs_record0 AS case_id,
            %(state_id)s AS state_id,
            LAST_VALUE(supervisor_id) over w as supervisor_id,
            %(month)s::DATE AS month,
            LAST_VALUE(timeend) over w AS latest_time_end_processed,
            LAST_VALUE(breastfed_at_birth) over w as breastfed_at_birth,
            SUM(CASE WHEN (unscheduled_visit=0 AND days_visit_late < 8) OR
                          (timeend::DATE - next_visit) < 8 THEN 1 ELSE 0 END
                ) OVER w as valid_visits,
            LAST_VALUE(where_born) OVER w AS where_born
          FROM "{ucr_tablename}"
          WHERE state_id = %(state_id)s AND
                timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND
                case_load_ccs_record0 IS NOT NULL
          WINDOW w AS (
            PARTITION BY supervisor_id, case_load_ccs_record0
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
          )
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table
        ), query_params
