from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, month_formatter
from custom.icds_reports.const import AGG_CHILD_HEALTH_PNC_TABLE


class PostnatalCareFormsChildHealthAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-postnatal_care_forms'
    aggregate_parent_table = AGG_CHILD_HEALTH_PNC_TABLE
    aggregate_child_table_prefix = 'icds_db_child_pnc_form_'

    @property
    def _old_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.child_health_monthly_ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def data_from_ucr_query(self):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        return """
        SELECT DISTINCT child_health_case_id AS case_id,
        LAST_VALUE(timeend) OVER w AS latest_time_end,
        MAX(counsel_increase_food_bf) OVER w AS counsel_increase_food_bf,
        MAX(counsel_breast) OVER w AS counsel_breast,
        MAX(skin_to_skin) OVER w AS skin_to_skin,
        LAST_VALUE(is_ebf) OVER w AS is_ebf,
        LAST_VALUE(water_or_milk) OVER w AS water_or_milk,
        LAST_VALUE(other_milk_to_child) OVER w AS other_milk_to_child,
        LAST_VALUE(tea_other) OVER w AS tea_other,
        LAST_VALUE(eating) OVER w AS eating,
        MAX(counsel_exclusive_bf) OVER w AS counsel_exclusive_bf,
        MAX(counsel_only_milk) OVER w AS counsel_only_milk,
        MAX(counsel_adequate_bf) OVER w AS counsel_adequate_bf,
        LAST_VALUE(not_breastfeeding) OVER w AS not_breastfeeding
        FROM "{ucr_tablename}"
        WHERE timeend >= %(current_month_start)s AND
              timeend < %(next_month_start)s AND
              state_id = %(state_id)s AND
              child_health_case_id IS NOT NULL
        WINDOW w AS (
            PARTITION BY child_health_case_id
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
          state_id, month, case_id, latest_time_end_processed, counsel_increase_food_bf,
          counsel_breast, skin_to_skin, is_ebf, water_or_milk, other_milk_to_child,
          tea_other, eating, counsel_exclusive_bf, counsel_only_milk, counsel_adequate_bf,
          not_breastfeeding
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            COALESCE(ucr.case_id, prev_month.case_id) AS case_id,
            GREATEST(ucr.latest_time_end, prev_month.latest_time_end_processed) AS latest_time_end_processed,
            GREATEST(ucr.counsel_increase_food_bf, prev_month.counsel_increase_food_bf) AS counsel_increase_food_bf,
            GREATEST(ucr.counsel_breast, prev_month.counsel_breast) AS counsel_breast,
            GREATEST(ucr.skin_to_skin, prev_month.skin_to_skin) AS skin_to_skin,
            ucr.is_ebf AS is_ebf,
            ucr.water_or_milk AS water_or_milk,
            ucr.other_milk_to_child AS other_milk_to_child,
            ucr.tea_other AS tea_other,
            ucr.eating AS eating,
            GREATEST(ucr.counsel_exclusive_bf, prev_month.counsel_exclusive_bf) AS counsel_exclusive_bf,
            GREATEST(ucr.counsel_only_milk, prev_month.counsel_only_milk) AS counsel_only_milk,
            GREATEST(ucr.counsel_adequate_bf, prev_month.counsel_adequate_bf) AS counsel_adequate_bf,
            ucr.not_breastfeeding AS not_breastfeeding
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
        FROM "{child_health_monthly_ucr}" chm_ucr
        FULL OUTER JOIN "{new_agg_table}" agg
        ON chm_ucr.doc_id = agg.case_id AND chm_ucr.month = agg.month AND agg.state_id = chm_ucr.state_id
        WHERE chm_ucr.month = %(month)s and agg.state_id = %(state_id)s AND (
              (chm_ucr.pnc_eligible = 1 AND (
                  chm_ucr.counsel_increase_food_bf != COALESCE(agg.counsel_increase_food_bf) OR
                  chm_ucr.counsel_manage_breast_problems != COALESCE(agg.counsel_breast, 0)
              )) OR
              (chm_ucr.ebf_eligible = 1 AND (
                  chm_ucr.ebf_in_month != COALESCE(agg.is_ebf, 0) OR
                  chm_ucr.ebf_drinking_liquid != (
                      GREATEST(agg.water_or_milk, agg.other_milk_to_child, agg.tea_other, 0)
                  ) OR
                  chm_ucr.ebf_eating != COALESCE(agg.eating, 0) OR
                  chm_ucr.ebf_not_breastfeeding_reason != COALESCE(agg.not_breastfeeding, 'not_breastfeeding') OR
                  chm_ucr.counsel_ebf != GREATEST(agg.counsel_exclusive_bf, agg.counsel_only_milk, 0) OR
                  chm_ucr.counsel_adequate_bf != GREATEST(agg.counsel_adequate_bf, 0)
              ))
        )
        """.format(
            child_health_monthly_ucr=self._old_ucr_tablename,
            new_agg_table=self.aggregate_parent_table,
        ), {
            "month": month.strftime('%Y-%m-%d'),
            "state_id": self.state_id
        }
