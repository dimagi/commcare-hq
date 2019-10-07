from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_CCS_RECORD_THR_TABLE
from custom.icds_reports.utils.aggregation_helpers import (
    month_formatter,
    transform_day_to_month,
)
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    BaseICDSAggregationDistributedHelper,
)


class THRFormsCcsRecordAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'thr-forms-ccs-record'
    ucr_data_source_id = 'static-dashboard_thr_forms'
    tablename = AGG_CCS_RECORD_THR_TABLE

    def __init__(self, month):
        self.month = transform_day_to_month(month)

    def aggregate(self, cursor):
        agg_query, agg_params = self.aggregation_query()

        cursor.execute(
            f'DELETE FROM "{self.tablename}" WHERE month=%(month)s',
            {'month': month_formatter(self.month)}
        )
        cursor.execute(agg_query, agg_params)

    def drop_table_query(self):
        raise NotImplementedError

    def aggregation_query(self):
        month = self.month.replace(day=1)
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        query_params = {
            "month": month_formatter(month),
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
        }

        return f"""
        INSERT INTO "{self.tablename}" (
          state_id, supervisor_id, month, case_id, latest_time_end_processed,
          days_ration_given_mother
        ) (
          SELECT DISTINCT ON (ccs_record_case_id)
            state_id,
            supervisor_id,
            %(month)s AS month,
            ccs_record_case_id as case_id,
            MAX(timeend) over w AS latest_time_end_processed,
            SUM(days_ration_given_mother) over w AS days_ration_given_mother
          FROM "{self.ucr_tablename}"
          WHERE state_id IS NOT NULL AND
                timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND
                ccs_record_case_id IS NOT NULL
          WINDOW w AS (
            PARTITION BY supervisor_id, ccs_record_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
          )
        )
        """, query_params
