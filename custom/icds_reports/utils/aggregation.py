from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import date
import hashlib

from dateutil.relativedelta import relativedelta

from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import (
    AGG_COMP_FEEDING_TABLE,
    AGG_CCS_RECORD_PNC_TABLE,
    AGG_CHILD_HEALTH_PNC_TABLE,
    AGG_CHILD_HEALTH_THR_TABLE,
    AGG_GROWTH_MONITORING_TABLE,
    DASHBOARD_DOMAIN
)
from six.moves import range


def transform_day_to_month(day):
    return day.replace(day=1)


def month_formatter(day):
    return transform_day_to_month(day).strftime('%Y-%m-%d')


class BaseICDSAggregationHelper(object):
    """Defines an interface for aggregating data from UCRs to specific tables
    for the dashboard.

    All aggregate tables are partitioned by state and month

    Attributes:
        ucr_data_source_id - The UCR data source that contains the raw data to aggregate
        aggregate_parent_table - The parent table defined in models.py that will contain aggregate data
        aggregate_child_table_prefix - The prefix for tables that inherit from the parent table
    """
    ucr_data_source_id = None
    aggregate_parent_table = None
    aggregate_child_table_prefix = None
    child_health_monthly_ucr_id = 'static-child_cases_monthly_tableau_v2'
    ccs_record_monthly_ucr_id = 'static-ccs_record_cases_monthly_tableau_v2'

    def __init__(self, state_id, month):
        self.state_id = state_id
        self.month = transform_day_to_month(month)

    @property
    def domain(self):
        # Currently its only possible for one domain to have access to the ICDS dashboard per env
        return DASHBOARD_DOMAIN

    @property
    def ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ucr_data_source_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def generate_child_tablename(self, month=None):
        month = month or self.month
        month_string = month_formatter(month)
        hash_for_table = hashlib.md5(self.state_id + month_string).hexdigest()[8:]
        return self.aggregate_child_table_prefix + hash_for_table

    def create_table_query(self, month=None):
        month = month or self.month
        month_string = month_formatter(month)
        tablename = self.generate_child_tablename(month)

        return """
        CREATE TABLE IF NOT EXISTS "{child_tablename}" (
            CHECK (month = %(month_string)s AND state_id = %(state_id)s),
            LIKE "{parent_tablename}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
        ) INHERITS ("{parent_tablename}")
        """.format(
            parent_tablename=self.aggregate_parent_table,
            child_tablename=tablename,
        ), {
            "month_string": month_string,
            "state_id": self.state_id
        }

    def drop_table_query(self):
        tablename = self.generate_child_tablename(self.month)
        return 'DROP TABLE IF EXISTS "{tablename}"'.format(tablename=tablename)

    def data_from_ucr_query(self):
        """Returns (SQL query, query parameters) from the UCR data table that
        puts data in the form expected by the aggregate table
        """
        raise NotImplementedError

    def aggregate_query(self):
        """Returns (SQL query, query parameters) that will aggregate from a UCR
        source to an aggregate table.
        """
        raise NotImplementedError

    def compare_with_old_data_query(self):
        """Used for backend migrations from one data source to another. Returns
        (SQL query, query parameters) that will return any rows that are
        inconsistent from the old data to the new.
        """
        raise NotImplementedError


class ComplementaryFormsAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-complementary_feeding_forms'
    aggregate_parent_table = AGG_COMP_FEEDING_TABLE
    aggregate_child_table_prefix = 'icds_db_child_cf_form_'

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
        MAX(play_comp_feeding_vid) OVER w AS play_comp_feeding_vid,
        MAX(comp_feeding) OVER w AS comp_feeding_ever,
        MAX(demo_comp_feeding) OVER w AS demo_comp_feeding,
        MAX(counselled_pediatric_ifa) OVER w AS counselled_pediatric_ifa,
        LAST_VALUE(comp_feeding) OVER w AS comp_feeding_latest,
        LAST_VALUE(diet_diversity) OVER w AS diet_diversity,
        LAST_VALUE(diet_quantity) OVER w AS diet_quantity,
        LAST_VALUE(hand_wash) OVER w AS hand_wash
        FROM "{ucr_tablename}"
        WHERE timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND state_id = %(state_id)s
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

        # GREATEST calculations are for when we want to know if a thing has
        # ever happened to a case.
        # CASE WHEN calculations are for when we want to know if a case
        # happened during the last form for this case. We must use CASE WHEN
        # and not COALESCE as when questions are skipped they will be NULL
        # and we want NULL in the aggregate table
        return """
        INSERT INTO "{tablename}" (
          state_id, month, case_id, latest_time_end_processed, comp_feeding_ever,
          demo_comp_feeding, counselled_pediatric_ifa, play_comp_feeding_vid,
          comp_feeding_latest, diet_diversity, diet_quantity, hand_wash
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            COALESCE(ucr.case_id, prev_month.case_id) AS case_id,
            GREATEST(ucr.latest_time_end, prev_month.latest_time_end_processed) AS latest_time_end_processed,
            GREATEST(ucr.comp_feeding_ever, prev_month.comp_feeding_ever) AS comp_feeding_ever,
            GREATEST(ucr.demo_comp_feeding, prev_month.demo_comp_feeding) AS demo_comp_feeding,
            GREATEST(ucr.counselled_pediatric_ifa, prev_month.counselled_pediatric_ifa) AS counselled_pediatric_ifa,
            GREATEST(ucr.play_comp_feeding_vid, prev_month.play_comp_feeding_vid) AS play_comp_feeding_vid,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.comp_feeding_latest ELSE prev_month.comp_feeding_latest
            END AS comp_feeding_latest,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.diet_diversity ELSE prev_month.diet_diversity
            END AS diet_diversity,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.diet_quantity ELSE prev_month.diet_quantity
            END AS diet_quantity,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.hand_wash ELSE prev_month.hand_wash
            END AS hand_wash
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
              (chm_ucr.cf_eligible = 1 AND (
                  chm_ucr.cf_in_month != agg.comp_feeding_latest OR
                  chm_ucr.cf_diet_diversity != agg.diet_diversity OR
                  chm_ucr.cf_diet_quantity != agg.diet_quantity OR
                  chm_ucr.cf_handwashing != agg.hand_wash OR
                  chm_ucr.cf_demo != agg.demo_comp_feeding OR
                  chm_ucr.counsel_pediatric_ifa != agg.counselled_pediatric_ifa OR
                  chm_ucr.counsel_comp_feeding_vid != agg.play_comp_feeding_vid
              )) OR (chm_ucr.cf_initiation_eligible = 1 AND chm_ucr.cf_initiated != agg.comp_feeding_ever)
        )
        """.format(
            child_health_monthly_ucr=self._old_ucr_tablename,
            new_agg_table=self.aggregate_parent_table,
        ), {
            "month": month.strftime('%Y-%m-%d'),
            "state_id": self.state_id
        }


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
        MAX(counsel_methods) OVER w AS counsel_methods
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
          state_id, month, case_id, latest_time_end_processed, counsel_methods
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            COALESCE(ucr.case_id, prev_month.case_id) AS case_id,
            GREATEST(ucr.latest_time_end, prev_month.latest_time_end_processed) AS latest_time_end_processed,
            GREATEST(ucr.counsel_methods, prev_month.counsel_methods) AS counsel_methods
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


class THRFormsChildHealthAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-dashboard_thr_forms'
    aggregate_parent_table = AGG_CHILD_HEALTH_THR_TABLE
    aggregate_child_table_prefix = 'icds_db_child_thr_form_'

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
          state_id, month, case_id, latest_time_end_processed, days_ration_given_child
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            child_health_case_id AS case_id,
            MAX(timeend) AS latest_time_end_processed,
            SUM(days_ration_given_child) AS days_ration_given_child
          FROM "{ucr_tablename}"
          WHERE state_id = %(state_id)s AND
                timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND
                child_health_case_id IS NOT NULL
          GROUP BY child_health_case_id
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename
        ), query_params


class GrowthMonitoringFormsAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-dashboard_growth_monitoring_forms'
    aggregate_parent_table = AGG_GROWTH_MONITORING_TABLE
    aggregate_child_table_prefix = 'icds_db_gm_form_'

    @property
    def _old_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.child_health_monthly_ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def data_from_ucr_query(self):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        # We need many windows here because we want the last time changed for each of these columns
        # Window definitions inspired by https://stackoverflow.com/a/47223416
        # The CASE/WHEN's are needed, because time end should be NULL when a form has not changed the value,
        # but the windows include all forms (this works because we use LAST_VALUE and NULLs are sorted to the top
        return """
            SELECT
                DISTINCT child_health_case_id AS case_id,
                LAST_VALUE(weight_child) OVER weight_child AS weight_child,
                CASE
                    WHEN LAST_VALUE(weight_child) OVER weight_child IS NULL THEN NULL
                    ELSE LAST_VALUE(timeend) OVER weight_child
                END AS weight_child_last_recorded,
                LAST_VALUE(height_child) OVER height_child AS height_child,
                CASE
                    WHEN LAST_VALUE(height_child) OVER height_child IS NULL THEN NULL
                    ELSE LAST_VALUE(timeend) OVER height_child
                END AS height_child_last_recorded,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfa) OVER zscore_grading_wfa = 0 THEN NULL
                    ELSE LAST_VALUE(zscore_grading_wfa) OVER zscore_grading_wfa
                END AS zscore_grading_wfa,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfa) OVER zscore_grading_wfa = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_wfa
                END AS zscore_grading_wfa_last_recorded,
                CASE
                    WHEN LAST_VALUE(zscore_grading_hfa) OVER zscore_grading_hfa = 0 THEN NULL
                    ELSE LAST_VALUE(zscore_grading_hfa) OVER zscore_grading_hfa
                END AS zscore_grading_hfa,
                CASE
                    WHEN LAST_VALUE(zscore_grading_hfa) OVER zscore_grading_hfa = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_hfa
                END AS zscore_grading_hfa_last_recorded,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfh) OVER zscore_grading_wfh = 0 THEN NULL
                    ELSE LAST_VALUE(zscore_grading_wfh) OVER zscore_grading_wfh
                END AS zscore_grading_wfh,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfh) OVER zscore_grading_wfh = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_wfh
                END AS zscore_grading_wfh_last_recorded,
                CASE
                    WHEN LAST_VALUE(muac_grading) OVER muac_grading = 0 THEN NULL
                    ELSE LAST_VALUE(muac_grading) OVER muac_grading
                END AS muac_grading,
                CASE
                    WHEN LAST_VALUE(muac_grading) OVER muac_grading = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER muac_grading
                END AS muac_grading_last_recorded
            FROM "{ucr_tablename}"
            WHERE timeend >= %(current_month_start)s AND timeend < %(next_month_start)s
                AND state_id = %(state_id)s AND child_health_case_id IS NOT NULL
            WINDOW
                weight_child AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN weight_child IS NULL THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                height_child AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN height_child IS NULL THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                zscore_grading_wfa AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN zscore_grading_wfa = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                zscore_grading_hfa AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN zscore_grading_hfa = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                zscore_grading_wfh AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN zscore_grading_wfh = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                muac_grading AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN muac_grading = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
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

        # The '1970-01-01' is a fallback, this should never happen,
        # but an unexpected NULL should not block other data
        return """
        INSERT INTO "{tablename}" (
            state_id, month, case_id, latest_time_end_processed,
            weight_child, weight_child_last_recorded,
            height_child, height_child_last_recorded,
            zscore_grading_wfa, zscore_grading_wfa_last_recorded,
            zscore_grading_hfa, zscore_grading_hfa_last_recorded,
            zscore_grading_wfh, zscore_grading_wfh_last_recorded,
            muac_grading, muac_grading_last_recorded
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            COALESCE(ucr.case_id, prev_month.case_id) AS case_id,
            GREATEST(
                ucr.weight_child_last_recorded,
                ucr.height_child_last_recorded,
                ucr.zscore_grading_wfa_last_recorded,
                ucr.zscore_grading_hfa_last_recorded,
                ucr.zscore_grading_wfh_last_recorded,
                ucr.muac_grading_last_recorded,
                prev_month.latest_time_end_processed,
                '1970-01-01'
            ) AS latest_time_end_processed,
            COALESCE(ucr.weight_child, prev_month.weight_child) AS weight_child,
            GREATEST(ucr.weight_child_last_recorded, prev_month.weight_child_last_recorded) AS weight_child_last_recorded,
            COALESCE(ucr.height_child, prev_month.height_child) AS height_child,
            GREATEST(ucr.height_child_last_recorded, prev_month.height_child_last_recorded) AS height_child_last_recorded,
            COALESCE(ucr.zscore_grading_wfa, prev_month.zscore_grading_wfa) AS zscore_grading_wfa,
            GREATEST(ucr.zscore_grading_wfa_last_recorded, prev_month.zscore_grading_wfa_last_recorded) AS zscore_grading_wfa_last_recorded,
            COALESCE(ucr.zscore_grading_hfa, prev_month.zscore_grading_hfa) AS zscore_grading_hfa,
            GREATEST(ucr.zscore_grading_hfa_last_recorded, prev_month.zscore_grading_hfa_last_recorded) AS zscore_grading_hfa_last_recorded,
            COALESCE(ucr.zscore_grading_wfh, prev_month.zscore_grading_wfh) AS zscore_grading_wfh,
            GREATEST(ucr.zscore_grading_wfh_last_recorded, prev_month.zscore_grading_wfh_last_recorded) AS zscore_grading_wfh_last_recorded,
            COALESCE(ucr.muac_grading, prev_month.muac_grading) AS muac_grading,
            GREATEST(ucr.muac_grading_last_recorded, prev_month.muac_grading_last_recorded) AS muac_grading_last_recorded
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
        # only partially implements this comparison for now
        month = self.month.replace(day=1)
        return """
        SELECT agg.case_id
        FROM "{child_health_monthly_ucr}" chm_ucr
        FULL OUTER JOIN "{new_agg_table}" agg
        ON chm_ucr.doc_id = agg.case_id AND chm_ucr.month = agg.month AND agg.state_id = chm_ucr.state_id
        WHERE chm_ucr.month = %(month)s and agg.state_id = %(state_id)s AND
              (chm_ucr.wer_eligible = 1 AND (
                 (chm_ucr.nutrition_status_last_recorded = 'severely_underweight' AND agg.zscore_grading_wfa = 1) OR
                 (chm_ucr.nutrition_status_last_recorded = 'moderately_underweight' AND agg.zscore_grading_wfa = 2) OR
                 (chm_ucr.nutrition_status_last_recorded = 'normal' AND agg.zscore_grading_wfa IN (3,4)) OR
                 (chm_ucr.nutrition_status_last_recorded IS NULL AND agg.zscore_grading_wfa = 0) OR
                 (chm_ucr.weight_recorded_in_month = agg.weight_child AND agg.latest_time_end_processed BETWEEN %(month)s AND %(next_month)s)
              ))
        """.format(
            child_health_monthly_ucr=self._old_ucr_tablename,
            new_agg_table=self.aggregate_parent_table,
        ), {
            "month": month.strftime('%Y-%m-%d'),
            "next_month": (month + relativedelta(month=1)).strftime('%Y-%m-%d'),
            "state_id": self.state_id
        }


def recalculate_aggregate_table(model_class):
    """Expects a class (not instance) of models.Model

    Not expected to last past 2018 (ideally past May) so this shouldn't break in 2019
    """
    state_ids = (
        SQLLocation.objects
        .filter(domain='icds-cas', location_type__name='state')
        .values_list('id', flat=True)
    )

    for state_id in state_ids:
        for year in (2015, 2016, 2017):
            for month in range(1, 13):
                model_class.aggregate(state_id, date(year, month, 1))

        for month in range(1, date.today().month + 1):
            model_class.aggregate(state_id, date(2018, month, 1))
