from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_DAILY_FEEDING_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class DailyFeedingFormsChildHealthAggregationHelper(BaseICDSAggregationHelper):
    helper_key = 'daily-feeding-forms-child-health'
    ucr_data_source_id = 'dashboard_child_health_daily_feeding_forms'
    aggregate_parent_table = AGG_DAILY_FEEDING_TABLE
    aggregate_child_table_prefix = 'icds_db_child_daily_feed_form_'

    def aggregate(self, cursor):
        curr_month_query, curr_month_params = self.create_table_query()
        agg_query, agg_params = self.aggregation_query()

        cursor.execute(self.drop_table_query())
        cursor.execute(curr_month_query, curr_month_params)
        cursor.execute(agg_query, agg_params)

    def aggregation_query(self):
        tablename = self.generate_child_tablename(self.month)
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        query_params = {
            "month": month_formatter(self.month),
            "state_id": self.state_id,
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
        }

        return """
        INSERT INTO "{tablename}" (
          state_id, supervisor_id, month, case_id, latest_time_end_processed,
          sum_attended_child_ids, lunch_count
        ) (
          SELECT DISTINCT ON (ucr.child_health_case_id)
            %(state_id)s AS state_id,
            LAST_VALUE(ucr.supervisor_id) OVER w AS supervisor_id,
            %(month)s AS month,
            ucr.child_health_case_id AS case_id,
            MAX(ucr.timeend) OVER w AS latest_time_end_processed,
            SUM(ucr.attended_child_ids) OVER w AS sum_attended_child_ids,
            SUM(ucr.lunch) OVER w AS lunch_count
          FROM "{ucr_tablename}" ucr inner join daily_attendance ON (
            ucr.doc_id = daily_attendance.doc_id AND
            daily_attendance.month=%(current_month_start)s
          )
          WHERE ucr.state_id = %(state_id)s AND
                ucr.timeend >= %(current_month_start)s AND ucr.timeend < %(next_month_start)s AND
                ucr.child_health_case_id IS NOT NULL
          WINDOW w AS (PARTITION BY ucr.child_health_case_id)
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename
        ), query_params
