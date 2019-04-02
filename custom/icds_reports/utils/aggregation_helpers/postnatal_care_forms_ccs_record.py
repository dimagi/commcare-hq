from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import AGG_CCS_RECORD_PNC_TABLE
from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, month_formatter


class PostnatalCareFormsCcsRecordAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-postnatal_care_forms'
    aggregate_parent_table = AGG_CCS_RECORD_PNC_TABLE
    aggregate_child_table_prefix = 'icds_db_ccs_pnc_form_'

    @property
    def _old_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ccs_record_monthly_ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def data_from_ucr_query(self):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        return """
        SELECT DISTINCT ccs_record_case_id AS case_id,
        LAST_VALUE(timeend) OVER w AS latest_time_end,
        MAX(counsel_methods) OVER w AS counsel_methods,
        LAST_VALUE(is_ebf) OVER w as is_ebf,
        SUM(CASE WHEN (unscheduled_visit=0 AND days_visit_late < 8) OR (timeend::DATE - next_visit) < 8 THEN 1 ELSE 0 END) OVER w as valid_visits,
        LAST_VALUE(supervisor_id) OVER w as supervisor_id
        FROM "{ucr_tablename}"
        WHERE timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND state_id = %(state_id)s
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

    def compare_with_old_data_query(self):
        """Compares data from the complementary feeding forms aggregate table
        to the the old child health monthly UCR table that current aggregate
        script uses
        """
        month = self.month.replace(day=1)
        return """
        SELECT agg.case_id
        FROM "{ccs_record_monthly_ucr}" crm_ucr
        FULL OUTER JOIN "{new_agg_table}" agg
        ON crm_ucr.doc_id = agg.case_id AND crm_ucr.month = agg.month AND agg.state_id = crm_ucr.state_id
        WHERE crm_ucr.month = %(month)s and agg.state_id = %(state_id)s AND (
              (crm_ucr.lactating = 1 OR crm_ucr.pregnant = 1) AND (
                crm_ucr.counsel_fp_methods != COALESCE(agg.counsel_methods, 0) OR
                (crm_ucr.pnc_visited_in_month = 1 AND
                 agg.latest_time_end_processed NOT BETWEEN %(month)s AND %(next_month)s)
              )
        )
        """.format(
            ccs_record_monthly_ucr=self._old_ucr_tablename,
            new_agg_table=self.aggregate_parent_table,
        ), {
            "month": month.strftime('%Y-%m-%d'),
            "next_month": (month + relativedelta(month=1)).strftime('%Y-%m-%d'),
            "state_id": self.state_id
        }
