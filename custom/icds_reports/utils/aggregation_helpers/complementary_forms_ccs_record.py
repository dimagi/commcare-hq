from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_CCS_RECORD_CF_TABLE
from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, month_formatter


class ComplementaryFormsCcsRecordAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-complementary_feeding_forms'
    aggregate_parent_table = AGG_CCS_RECORD_CF_TABLE
    aggregate_child_table_prefix = 'icds_db_child_ccs_cf_form_'

    def data_from_ucr_query(self):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        return """
        SELECT DISTINCT ccs_record_case_id AS case_id,
        LAST_VALUE(timeend) OVER w AS latest_time_end,
        SUM(CASE WHEN (unscheduled_visit=0 AND days_visit_late < 8) OR (timeend::DATE - next_visit) < 8 THEN 1 ELSE 0 END) OVER w as valid_visits
        FROM "{ucr_tablename}"
        WHERE (
          timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND
          state_id = %(state_id)s AND ccs_record_case_id IS NOT NULL
        )
        WINDOW w AS (
            PARTITION BY ccs_record_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
        """.format(ucr_tablename=self.ucr_tablename), {
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
            "state_id": self.state_id
        }

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)
        previous_month_tablename = self.generate_child_tablename(month - relativedelta(months=1))

        ucr_query, ucr_query_params = self.data_from_ucr_query()
        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id
        }
        query_params.update(ucr_query_params)

        return """
        INSERT INTO "{tablename}" (
          state_id, month, case_id, latest_time_end_processed, valid_visits
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            COALESCE(ucr.case_id, prev_month.case_id) AS case_id,
            GREATEST(ucr.latest_time_end, prev_month.latest_time_end_processed) AS latest_time_end_processed,
          COALESCE(ucr.valid_visits, 0) as valid_visits
          FROM ({ucr_table_query}) ucr
          FULL OUTER JOIN "{previous_month_tablename}" prev_month
          ON ucr.case_id = prev_month.case_id
        )
        """.format(
            ucr_table_query=ucr_query,
            previous_month_tablename=previous_month_tablename,
            tablename=tablename
        ), query_params
