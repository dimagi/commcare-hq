from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import AGG_CCS_RECORD_BP_TABLE
from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, month_formatter


class BirthPreparednessFormsAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-dashboard_birth_preparedness_forms'
    aggregate_parent_table = AGG_CCS_RECORD_BP_TABLE
    aggregate_child_table_prefix = 'icds_db_bp_form_'

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
        MAX(immediate_breastfeeding) OVER w AS immediate_breastfeeding,
        LAST_VALUE(eating_extra) OVER w as eating_extra,
        LAST_VALUE(resting) OVER w as resting,
        LAST_VALUE(anc_weight) OVER w as anc_weight,
        LAST_VALUE(anc_blood_pressure) OVER w as anc_blood_pressure,
        LAST_VALUE(bp_sys) OVER w as bp_sys,
        LAST_VALUE(bp_dia) OVER w as bp_dia,
        LAST_VALUE(anc_hemoglobin) OVER w as anc_hemoglobin,
        LAST_VALUE(bleeding) OVER w as bleeding,
        LAST_VALUE(swelling) OVER w as swelling,
        LAST_VALUE(blurred_vision) OVER w as blurred_vision,
        LAST_VALUE(convulsions) OVER w as convulsions,
        LAST_VALUE(rupture) OVER w as rupture,
        LAST_VALUE(anemia) OVER w as anemia,
        LAST_VALUE(anc_abnormalities) OVER w as anc_abnormalities,
        SUM(CASE WHEN unscheduled_visit=0 AND days_visit_late < 8 THEN 1 ELSE 0 END) OVER w as valid_visits
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
          state_id, month, case_id, latest_time_end_processed,
          immediate_breastfeeding, anemia, eating_extra, resting,
          anc_weight, anc_blood_pressure, bp_sys, bp_dia, anc_hemoglobin, 
          bleeding, swelling, blurred_vision, convulsions, rupture, anc_abnormalities, valid_visits
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            ucr.case_id AS case_id,
            ucr.latest_time_end AS latest_time_end_processed,
            GREATEST(ucr.immediate_breastfeeding, prev_month.immediate_breastfeeding) AS immediate_breastfeeding,
            ucr.anemia AS anemia,
            ucr.eating_extra AS eating_extra,
            ucr.resting AS resting,
            ucr.anc_weight anc_weight,
            ucr.anc_blood_pressure as anc_blood_pressure,
            ucr.bp_sys as bp_sys,
            ucr.bp_dia as bp_dia,
            ucr.anc_hemoglobin as anc_hemoglobin,
            ucr.bleeding as bleeding,
            ucr.swelling as swelling,
            ucr.blurred_vision as blurred_vision,
            ucr.convulsions as convulsions,
            ucr.rupture as rupture,
            ucr.anc_abnormalities as anc_abnormalities,
            COALESCE(ucr.valid_visits, 0) as valid_visits
          FROM ({ucr_table_query}) ucr
          LEFT JOIN "{previous_month_tablename}" prev_month
          ON ucr.case_id = prev_month.case_id
        )
        """.format(
            ucr_table_query=ucr_query,
            previous_month_tablename=previous_month_tablename,
            tablename=tablename
        ), query_params

    def compare_with_old_data_query(self):
        month = self.month.replace(day=1)
        return """
        SELECT agg.case_id
        FROM "{ccs_record_monthly_ucr}" ccs_ucr
        FULL OUTER JOIN "{new_agg_table}" agg
        ON ccs_ucr.doc_id = agg.case_id AND ccs_ucr.month = agg.month AND agg.state_id = ccs_ucr.state_id
        WHERE ccs_ucr.month = %(month)s and agg.state_id = %(state_id)s AND
              (ccs_ucr.pregnant = 1 AND (
                 (ccs_ucr.anemic_severe = 1 AND agg.anemia != 1) OR
                 (ccs_ucr.anemic_moderate = 1 AND agg.anemia != 2) OR
                 (ccs_ucr.anemic_normal = 1 AND agg.anemia != 3) OR
                 (ccs_ucr.anemic_unknown = 1 AND agg.anemia != 0) OR
                 ccs_ucr.extra_meal != agg.eating_extra OR
                 ccs_ucr.resting_during_pregnancy != agg.resting
              )) AND
              (ccs_ucr.pregnant = 1 AND trimester = 3 AND (
                 ccs_ucr.counsel_immediate_bf != agg.immediate_breastfeeding
              ))
        """.format(
            ccs_record_monthly_ucr=self._old_ucr_tablename,
            new_agg_table=self.aggregate_parent_table,
        ), {
            "month": month.strftime('%Y-%m-%d'),
            "next_month": (month + relativedelta(month=1)).strftime('%Y-%m-%d'),
            "state_id": self.state_id
        }
