from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_CCS_RECORD_THR_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class THRFormsCcsRecordAggregationHelper(BaseICDSAggregationHelper):
    helper_key = 'thr-forms-ccs-record'
    ucr_data_source_id = 'static-dashboard_thr_forms'
    aggregate_parent_table = AGG_CCS_RECORD_THR_TABLE
    aggregate_child_table_prefix = 'icds_db_ccs_thr_form_'

    def aggregate(self, cursor):
        curr_month_query, curr_month_params = self.create_table_query()
        agg_query, agg_params = self.aggregation_query()

        cursor.execute(self.drop_table_query())
        cursor.execute(curr_month_query, curr_month_params)
        cursor.execute(agg_query, agg_params)

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)
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
          state_id, supervisor_id, month, case_id, latest_time_end_processed,
          days_ration_given_mother
        ) (
          SELECT DISTINCT ON (ccs_record_case_id)
            %(state_id)s AS state_id,
            LAST_VALUE(supervisor_id) over w as supervisor_id,
            %(month)s AS month,
            ccs_record_case_id as case_id,
            MAX(timeend) over w AS latest_time_end_processed,
            SUM(days_ration_given_mother) over w AS days_ration_given_mother
          FROM "{ucr_tablename}"
          WHERE state_id = %(state_id)s AND
                timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND
                ccs_record_case_id IS NOT NULL
          WINDOW w AS (
            PARTITION BY ccs_record_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
          )
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename
        ), query_params
