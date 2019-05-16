from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import AGG_CCS_RECORD_PNC_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class PostnatalCareFormsCcsRecordAggregationHelper(BaseICDSAggregationHelper):
    helper_key = 'postnatal-care-forms-ccs-record'
    ucr_data_source_id = 'static-postnatal_care_forms'
    aggregate_parent_table = AGG_CCS_RECORD_PNC_TABLE
    aggregate_child_table_prefix = 'icds_db_ccs_pnc_form_'

    def aggregate(self, cursor):
        prev_month_query, prev_month_params = self.create_table_query(self.month - relativedelta(months=1))
        curr_month_query, curr_month_params = self.create_table_query()
        agg_query, agg_params = self.aggregation_query()

        cursor.execute(prev_month_query, prev_month_params)
        cursor.execute(self.drop_table_query())
        cursor.execute(curr_month_query, curr_month_params)
        cursor.execute(agg_query, agg_params)

    def data_from_ucr_query(self):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        return """
        SELECT
        distinct case_id,
        LAST_VALUE(latest_time_end) OVER w AS latest_time_end,
        MAX(counsel_methods) OVER w AS counsel_methods,
        LAST_VALUE(is_ebf) OVER w as is_ebf,
        SUM(CASE WHEN (unscheduled_visit=0 AND days_visit_late < 8) OR
        (latest_time_end::DATE - next_visit) < 8 THEN 1 ELSE 0 END) OVER w as valid_visits,
        LAST_VALUE(supervisor_id) OVER w as supervisor_id
        from
        (
            SELECT
                DISTINCT ccs_record_case_id AS case_id,
                LAST_VALUE(timeend) OVER w AS latest_time_end,
                MAX(counsel_methods) OVER w AS counsel_methods,
                LAST_VALUE(is_ebf) OVER w as is_ebf,
                LAST_VALUE(unscheduled_visit) OVER w as unscheduled_visit,
                LAST_VALUE(days_visit_late) OVER w as days_visit_late,
                LAST_VALUE(next_visit) OVER w as next_visit,
                LAST_VALUE(supervisor_id) OVER w as supervisor_id
                FROM "{ucr_tablename}"
                WHERE timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND state_id = %(state_id)s
                WINDOW w AS (
                    PARTITION BY doc_id, ccs_record_case_id
                    ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                )
        ) ut
        WINDOW w AS (
            PARTITION BY case_id
            ORDER BY latest_time_end RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
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
          state_id, supervisor_id, month, case_id, latest_time_end_processed, counsel_methods, is_ebf,
          valid_visits
        ) (
          SELECT
            %(state_id)s AS state_id,
            COALESCE(ucr.supervisor_id, prev_month.supervisor_id) as supervisor_id,
            %(month)s AS month,
            COALESCE(ucr.case_id, prev_month.case_id) AS case_id,
            GREATEST(ucr.latest_time_end, prev_month.latest_time_end_processed) AS latest_time_end_processed,
            GREATEST(ucr.counsel_methods, prev_month.counsel_methods) AS counsel_methods,
            ucr.is_ebf as is_ebf,
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
