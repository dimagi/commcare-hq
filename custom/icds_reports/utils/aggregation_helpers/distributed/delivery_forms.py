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
    months_required = 0

    def aggregation_query(self):
        month = self.month.replace(day=1)
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))
        prev_month_start = month_formatter(self.month - relativedelta(months=1))

        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id,
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
            "prev_month_start": prev_month_start
        }

        return """
        INSERT INTO "{tablename}" (
          case_id, state_id, supervisor_id, month, latest_time_end_processed,
          breastfed_at_birth, valid_visits, where_born, num_children_del, still_live_birth
        ) (
          SELECT
            DISTINCT ucr.case_load_ccs_record0 AS case_id,
            %(state_id)s AS state_id,
            LAST_VALUE(ucr.supervisor_id) over w as supervisor_id,
            %(month)s::DATE AS month,
            LAST_VALUE(ucr.timeend_with_time) over w AS latest_time_end_processed,
            LAST_VALUE(ucr.breastfed_at_birth) over w as breastfed_at_birth,
            COALESCE(LAST_VALUE(ucr.breastfed_at_birth) over w , prev_month.breastfed_at_birth) as breastfed_at_birth_original_status,
            SUM(CASE WHEN (ucr.unscheduled_visit=0 AND ucr.days_visit_late < 8) OR
                          (ucr.timeend_with_time::DATE - ucr.next_visit) < 8 THEN 1 ELSE 0 END
                ) OVER w as valid_visits,
            LAST_VALUE(ucr.where_born) OVER w AS where_born,
            LAST_VALUE(ucr.num_children_del) OVER w AS num_children_del,
            LAST_VALUE(ucr.still_live_birth) OVER w AS still_live_birth
          FROM ({ucr_tablename}) ucr 
          FULL OUTER JOIN (
            SELECT * FROM {ucr_tablename} where MONTH = %(prev_month_start)s
          ) prev_month
          ON ucr.supervisor_id = prev_month.supervisor_id AND
          ucr.case_load_ccs_record0 = prev_month.case_load_ccs_record0
          WHERE ucr.state_id = %(state_id)s AND
                ucr.timeend_with_time >= %(current_month_start)s AND ucr.timeend_with_time < %(next_month_start)s AND
                ucr.case_load_ccs_record0 IS NOT NULL
          WINDOW w AS (
            PARTITION BY ucr.supervisor_id, ucr.case_load_ccs_record0
            ORDER BY ucr.timeend_with_time RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
          )
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table
        ), query_params
