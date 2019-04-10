from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_CCS_RECORD_CF_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper


class ComplementaryFormsCcsRecordAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'complementary-forms-ccs-record'
    ucr_data_source_id = 'static-complementary_feeding_forms'
    tablename = AGG_CCS_RECORD_CF_TABLE

    def aggregate(self, cursor):
        drop_query, drop_params = self.drop_table_query()
        agg_query, agg_params = self.aggregation_query()

        cursor.execute(drop_query, drop_params)
        cursor.execute(agg_query, agg_params)

    def drop_table_query(self):
        return (
            'DELETE FROM "{}" WHERE month=%(month)s AND state_id = %(state)s'.format(self.tablename),
            {'month': month_formatter(self.month), 'state': self.state_id}
        )

    def data_from_ucr_query(self):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        return """
        SELECT DISTINCT ccs_record_case_id AS case_id,
        %(current_month_start)s as month,
        LAST_VALUE(timeend) OVER w AS latest_time_end,
        SUM(
            CASE WHEN (unscheduled_visit=0 AND days_visit_late < 8) OR (timeend::DATE - next_visit) < 8
            THEN 1 ELSE 0 END
        ) OVER w as valid_visits,
        supervisor_id as supervisor_id
        FROM "{ucr_tablename}"
        WHERE (
          timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND
          state_id = %(state_id)s AND ccs_record_case_id IS NOT NULL
        )
        WINDOW w AS (
            PARTITION BY supervisor_id, ccs_record_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
        """.format(ucr_tablename=self.ucr_tablename), {
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
            "state_id": self.state_id
        }

    def aggregation_query(self):
        month = self.month.replace(day=1)

        ucr_query, ucr_query_params = self.data_from_ucr_query()
        query_params = {
            "month": month_formatter(month),
            "previous_month": month_formatter(month - relativedelta(months=1)),
            "state_id": self.state_id
        }
        query_params.update(ucr_query_params)

        return """
        INSERT INTO "{tablename}" (
          state_id, month, supervisor_id, case_id, latest_time_end_processed, valid_visits
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            COALESCE(ucr.supervisor_id, prev_month.supervisor_id) as supervisor_id,
            COALESCE(ucr.case_id, prev_month.case_id) AS case_id,
            GREATEST(ucr.latest_time_end, prev_month.latest_time_end_processed) AS latest_time_end_processed,
          COALESCE(ucr.valid_visits, 0) as valid_visits
          FROM ({ucr_table_query}) ucr
          FULL OUTER JOIN "{tablename}" prev_month
          ON ucr.case_id = prev_month.case_id AND ucr.supervisor_id = prev_month.supervisor_id
            AND ucr.month::DATE=prev_month.month + INTERVAL '1 month'
          WHERE coalesce(ucr.month, %(month)s) = %(month)s
            AND coalesce(prev_month.month, %(previous_month)s) = %(previous_month)s
            AND coalesce(prev_month.state_id, %(state_id)s) = %(state_id)s
        )
        """.format(
            ucr_table_query=ucr_query,
            tablename=self.tablename
        ), query_params
