from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_DAILY_FEEDING_TABLE
from custom.icds_reports.utils.aggregation_helpers import (
    month_formatter,
    transform_day_to_month,
)
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    BaseICDSAggregationDistributedHelper,
)


class DailyFeedingFormsChildHealthAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'daily-feeding-forms-child-health'
    ucr_data_source_id = 'dashboard_child_health_daily_feeding_forms'
    tablename = AGG_DAILY_FEEDING_TABLE

    def __init__(self, month):
        self.month = transform_day_to_month(month)

    def aggregate(self, cursor):
        drop_query, drop_params = self.drop_table_query()
        agg_query, agg_params = self.aggregation_query()

        cursor.execute(drop_query, drop_params)
        cursor.execute(agg_query, agg_params)

    def drop_table_query(self):
        return (
            f'DELETE FROM "{self.tablename}" WHERE month=%(month)s',
            {'month': month_formatter(self.month)}
        )

    def aggregation_query(self):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        query_params = {
            "month": month_formatter(self.month),
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
        }

        return f"""
        INSERT INTO "{self.tablename}" (
          state_id, supervisor_id, month, case_id, latest_time_end_processed,
          sum_attended_child_ids, lunch_count
        ) (
          SELECT DISTINCT ON (ucr.child_health_case_id)
            ucr.state_id AS state_id,
            ucr.supervisor_id,
            %(month)s AS month,
            ucr.child_health_case_id AS case_id,
            MAX(ucr.timeend) OVER w AS latest_time_end_processed,
            SUM(ucr.attended_child_ids) OVER w AS sum_attended_child_ids,
            SUM(ucr.lunch) OVER w AS lunch_count
          FROM "{self.ucr_tablename}" ucr INNER JOIN daily_attendance ON (
            ucr.doc_id = daily_attendance.doc_id AND
            ucr.supervisor_id = daily_attendance.supervisor_id AND
            daily_attendance.month=%(current_month_start)s
          )
          WHERE ucr.timeend >= %(current_month_start)s AND ucr.timeend < %(next_month_start)s AND
                ucr.child_health_case_id IS NOT NULL
          WINDOW w AS (PARTITION BY ucr.supervisor_id, ucr.child_health_case_id)
        )
        """, query_params
