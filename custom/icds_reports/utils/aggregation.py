from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
from datetime import date
import hashlib

from dateutil.relativedelta import relativedelta
from django.utils.functional import cached_property
import six

from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import (
    AGG_COMP_FEEDING_TABLE,
    AGG_CCS_RECORD_PNC_TABLE,
    AGG_CHILD_HEALTH_PNC_TABLE,
    AGG_CHILD_HEALTH_THR_TABLE,
    AGG_DAILY_FEEDING_TABLE,
    AGG_GROWTH_MONITORING_TABLE,
    DASHBOARD_DOMAIN,
)
from six.moves import range
from six.moves import map


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
        .values_list('location_id', flat=True)
    )

    for state_id in state_ids:
        for year in (2015, 2016, 2017):
            for month in range(1, 13):
                model_class.aggregate(state_id, date(year, month, 1))

        for month in range(1, date.today().month + 1):
            model_class.aggregate(state_id, date(2018, month, 1))


class ChildHealthMonthlyAggregationHelper(BaseICDSAggregationHelper):
    base_tablename = 'child_health_monthly'

    def __init__(self, month):
        self.month = transform_day_to_month(month)

    @property
    def child_health_monthly_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.child_health_monthly_ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def child_health_case_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-child_health_cases')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def child_tasks_case_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-child_tasks_cases')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def tablename(self):
        return "{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"))

    def drop_table_query(self):
        return 'DELETE FROM "{}"'.format(self.tablename)

    def aggregation_query(self):
        columns = (
            ("awc_id", "ucr.awc_id"),
            ("case_id", "ucr.case_id"),
            ("month", "ucr.month"),
            ("sex", "ucr.sex"),
            ("age_tranche", "ucr.age_tranche"),
            ("caste", "ucr.caste"),
            ("disabled", "ucr.disabled"),
            ("minority", "ucr.minority"),
            ("resident", "ucr.resident"),
            ("dob", "ucr.dob"),
            ("age_in_months", "ucr.age_in_months"),
            ("open_in_month", "ucr.open_in_month"),
            ("alive_in_month", "ucr.alive_in_month"),
            ("born_in_month", "ucr.born_in_month"),
            ("bf_at_birth_born_in_month", "ucr.bf_at_birth_born_in_month"),
            ("fully_immunized_eligible", "ucr.fully_immunized_eligible"),
            ("fully_immunized_on_time", "ucr.fully_immunized_on_time"),
            ("fully_immunized_late", "ucr.fully_immunized_late"),
            ("has_aadhar_id", "ucr.has_aadhar_id"),
            ("valid_in_month", "ucr.valid_in_month"),
            ("valid_all_registered_in_month", "ucr.valid_all_registered_in_month"),
            ("person_name", "child_health.person_name"),
            ("mother_name", "child_health.mother_name"),
            # PSE/DF Indicators
            ("pse_eligible", "ucr.pse_eligible"),
            ("pse_days_attended",
                "CASE WHEN ucr.pse_eligible = 1 THEN COALESCE(df.sum_attended_child_ids, 0) ELSE NULL END"),
            # EBF Indicators
            ("ebf_eligible", "ucr.ebf_eligible"),
            ("ebf_in_month", "CASE WHEN ucr.ebf_eligible = 1 THEN COALESCE(pnc.is_ebf, 0) ELSE 0 END"),
            ("ebf_not_breastfeeding_reason",
                "CASE WHEN ucr.ebf_eligible = 1 THEN pnc.not_breastfeeding ELSE NULL END"),
            ("ebf_drinking_liquid",
                "CASE WHEN ucr.ebf_eligible = 1 THEN GREATEST(pnc.water_or_milk, pnc.other_milk_to_child, pnc.tea_other, 0) ELSE 0 END"),
            ("ebf_eating",
                "CASE WHEN ucr.ebf_eligible = 1 THEN COALESCE(pnc.eating, 0) ELSE 0 END"),
            ("ebf_no_bf_no_milk", "0"),
            ("ebf_no_bf_pregnant_again", "0"),
            ("ebf_no_bf_child_too_old", "0"),
            ("ebf_no_bf_mother_sick", "0"),
            ("counsel_adequate_bf",
                "CASE WHEN ucr.ebf_eligible = 1 THEN COALESCE(pnc.counsel_adequate_bf, 0) ELSE 0 END"),
            ("ebf_no_info_recorded",
                """CASE WHEN ucr.ebf_eligible = 1 AND date_trunc('MONTH', pnc.latest_time_end_processed) = %(start_date)s THEN 0 ELSE ucr.ebf_eligible END"""),
            ("counsel_ebf",
                "CASE WHEN ucr.ebf_eligible = 1 THEN GREATEST(pnc.counsel_exclusive_bf, pnc.counsel_only_milk, 0) ELSE 0 END"),
            # PNC Indicators
            ("pnc_eligible", "ucr.pnc_eligible"),
            ("counsel_increase_food_bf",
                "CASE WHEN ucr.pnc_eligible = 1 THEN COALESCE(pnc.counsel_increase_food_bf, 0) ELSE 0 END"),
            ("counsel_manage_breast_problems",
                "CASE WHEN ucr.pnc_eligible = 1 THEN COALESCE(pnc.counsel_breast, 0) ELSE 0 END"),
            ("counsel_skin_to_skin",
                "CASE WHEN ucr.pnc_eligible = 1 THEN COALESCE(pnc.skin_to_skin, 0) ELSE 0 END"),
            # GM Indicators
            ("low_birth_weight_born_in_month", "ucr.low_birth_weight_born_in_month"),
            ("wer_eligible", "ucr.wer_eligible"),
            ("nutrition_status_last_recorded", "ucr.nutrition_status_last_recorded"),
            ("current_month_nutrition_status", "ucr.current_month_nutrition_status"),
            ("nutrition_status_weighed", "ucr.nutrition_status_weighed"),
            ("recorded_weight", "ucr.weight_recorded_in_month"),
            ("recorded_height",
                "COALESCE(CASE WHEN (date_trunc('MONTH', gm.height_child_last_recorded) = %(start_date)s) THEN gm.height_child ELSE NULL END, ucr.height_recorded_in_month)"),
            ("height_measured_in_month",
                "COALESCE(CASE WHEN (date_trunc('MONTH', gm.height_child_last_recorded) = %(start_date)s) THEN 1 ELSE NULL END, ucr.height_measured_in_month)"),
            ("current_month_stunting", "ucr.current_month_stunting"),
            ("stunting_last_recorded", "ucr.stunting_last_recorded"),
            ("wasting_last_recorded", "ucr.wasting_last_recorded"),
            ("current_month_wasting", "ucr.current_month_wasting"),
            ("zscore_grading_hfa", "gm.zscore_grading_hfa"),
            ("zscore_grading_hfa_recorded_in_month",
                "CASE WHEN (date_trunc('MONTH', gm.zscore_grading_hfa_last_recorded) = %(start_date)s) THEN 1 ELSE 0 END"),
            ("zscore_grading_wfh", "gm.zscore_grading_wfh"),
            ("zscore_grading_wfh_recorded_in_month",
                "CASE WHEN (date_trunc('MONTH', gm.zscore_grading_wfh_last_recorded) = %(start_date)s) THEN 1 ELSE 0 END"),
            ("muac_grading", "gm.muac_grading"),
            ("muac_grading_recorded_in_month",
                "CASE WHEN (date_trunc('MONTH', gm.muac_grading_last_recorded) = %(start_date)s) THEN 1 ELSE 0 END"),
            # CF Indicators
            ("cf_eligible", "ucr.cf_eligible"),
            ("cf_initiation_eligible", "ucr.cf_initiation_eligible"),
            ("cf_in_month", "CASE WHEN ucr.cf_eligible = 1 THEN COALESCE(cf.comp_feeding_latest, 0) ELSE 0 END"),
            ("cf_diet_diversity", "CASE WHEN ucr.cf_eligible = 1 THEN COALESCE(cf.diet_diversity, 0) ELSE 0 END"),
            ("cf_diet_quantity", "CASE WHEN ucr.cf_eligible = 1 THEN COALESCE(cf.diet_quantity, 0) ELSE 0 END"),
            ("cf_handwashing", "CASE WHEN ucr.cf_eligible = 1 THEN COALESCE(cf.hand_wash, 0) ELSE 0 END"),
            ("cf_demo", "CASE WHEN ucr.cf_eligible = 1 THEN COALESCE(cf.demo_comp_feeding, 0) ELSE 0 END"),
            ("counsel_pediatric_ifa",
                "CASE WHEN ucr.cf_eligible = 1 THEN COALESCE(cf.counselled_pediatric_ifa, 0) ELSE 0 END"),
            ("counsel_comp_feeding_vid",
                "CASE WHEN ucr.cf_eligible = 1 THEN COALESCE(cf.play_comp_feeding_vid, 0) ELSE 0 END"),
            ("cf_initiation_in_month",
                "CASE WHEN ucr.cf_initiation_eligible = 1 THEN COALESCE(cf.comp_feeding_ever, 0) ELSE 0 END"),
            # THR Indicators
            ("thr_eligible", "ucr.thr_eligible"),
            ("num_rations_distributed",
                "CASE WHEN ucr.thr_eligible = 1 THEN COALESCE(thr.days_ration_given_child, 0) ELSE NULL END"),
            ("days_ration_given_child", "thr.days_ration_given_child"),
            # Tasks case Indicators
            ("immunization_in_month", """
                  CASE WHEN
                      date_trunc('MONTH', child_tasks.due_list_date_1g_dpt_1) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_dpt_2) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_dpt_3) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_dpt_booster) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_dpt_booster1) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_7gdpt_booster_2) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_0g_hep_b_0) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_hep_b_1) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_hep_b_2) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_hep_b_3) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_ipv) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_je_1) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_je_2) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_measles_booster) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_measles) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_penta_1) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_penta_2) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_penta_3) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_rv_1) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_rv_2) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_rv_3) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_vit_a_1) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_vit_a_2) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_3) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_4) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_5) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_6) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_7) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_8) = %(start_date)s OR
                      date_trunc('MONTH', child_tasks.due_list_date_7g_vit_a_9) = %(start_date)s
                  THEN 1 ELSE NULL END
            """),
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (SELECT
            {calculations}
            FROM "{ucr_child_monthly_table}" ucr
            LEFT OUTER JOIN "{agg_cf_table}" cf ON ucr.doc_id = cf.case_id AND ucr.month = cf.month
            LEFT OUTER JOIN "{agg_thr_table}" thr ON ucr.doc_id = thr.case_id AND ucr.month = thr.month
            LEFT OUTER JOIN "{agg_gm_table}" gm ON ucr.doc_id = gm.case_id AND ucr.month = gm.month
            LEFT OUTER JOIN "{agg_pnc_table}" pnc ON ucr.doc_id = pnc.case_id AND ucr.month = pnc.month
            LEFT OUTER JOIN "{agg_df_table}" df ON ucr.doc_id = df.case_id AND ucr.month = df.month
            LEFT OUTER JOIN "{child_health_case_ucr}" child_health ON ucr.doc_id = child_health.doc_id
            LEFT OUTER JOIN "{child_tasks_case_ucr}" child_tasks ON ucr.doc_id = child_tasks.child_health_case_id
            WHERE ucr.month = %(start_date)s
            ORDER BY ucr.awc_id, ucr.case_id
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            ucr_child_monthly_table=self.child_health_monthly_ucr_tablename,
            agg_cf_table=AGG_COMP_FEEDING_TABLE,
            agg_thr_table=AGG_CHILD_HEALTH_THR_TABLE,
            child_health_case_ucr=self.child_health_case_ucr_tablename,
            agg_gm_table=AGG_GROWTH_MONITORING_TABLE,
            agg_pnc_table=AGG_CHILD_HEALTH_PNC_TABLE,
            agg_df_table=AGG_DAILY_FEEDING_TABLE,
            child_tasks_case_ucr=self.child_tasks_case_ucr_tablename,
        ), {
            "start_date": self.month
        }

    def indexes(self):
        return [
            'CREATE INDEX ON "{}" (case_id)'.format(self.tablename),
            'CREATE INDEX ON "{}" (awc_id)'.format(self.tablename),
        ]


class InactiveAwwsAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-usage_forms'

    def __init__(self, last_sync):
        self.last_sync = last_sync

    @cached_property
    def aggregate_parent_table(self):
        from custom.icds_reports.models import AggregateInactiveAWW
        return AggregateInactiveAWW._meta.db_table

    def data_from_ucr_query(self):
        return """
            SELECT DISTINCT awc_id as awc_id,
                FIRST_VALUE(form_date) OVER forms as first_submission,
                LAST_VALUE(form_date) OVER forms as last_submission
            FROM "{ucr_tablename}"
            WHERE inserted_at >= %(last_sync)s AND form_date <= %(now)s
            WINDOW forms AS (
              PARTITION BY awc_id
              ORDER BY form_date ASC RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
        """.format(
            ucr_tablename=self.ucr_tablename,
        ), {
            "last_sync": self.last_sync,
            "now": datetime.datetime.utcnow()
        }

    def missing_location_query(self):
        return """
        INSERT INTO "{table_name}" (
            awc_id, awc_name, awc_site_code, supervisor_id, supervisor_name,
            block_id, block_name, district_id, district_name, state_id, state_name
        ) (
            SELECT
                loc.doc_id as awc_id,
                loc.awc_name as awc_name,
                'awc' || loc.awc_site_code as awc_site_code,
                loc.supervisor_id as supervisor_id,
                loc.supervisor_name as supervisor_name,
                loc.block_id as block_id,
                loc.block_name as block_name,
                loc.district_id as district_id,
                loc.district_name as district_name,
                loc.state_id as state_id,
                loc.state_name as state_name
            FROM "{awc_location_table_name}" loc
            WHERE loc.doc_id not in (
              SELECT aww.awc_id FROM "{table_name}" aww
            ) and loc.doc_id != 'All'
        )
        """.format(
            table_name=self.aggregate_parent_table,
            awc_location_table_name='awc_location'
        )

    def aggregate_query(self):
        ucr_query, params = self.data_from_ucr_query()
        return """
            UPDATE "{table_name}" AS agg_table SET
                first_submission = LEAST(agg_table.first_submission, ut.first_submission),
                last_submission = GREATEST(agg_table.last_submission, ut.last_submission)
            FROM (
              SELECT
                loc.doc_id as awc_id,
                ucr.first_submission as first_submission,
                ucr.last_submission as last_submission
              FROM ({ucr_table_query}) ucr
              JOIN "{awc_location_table_name}" loc
              ON ucr.awc_id = loc.doc_id
            ) ut
            WHERE agg_table.awc_id = ut.awc_id
        """.format(
            table_name=self.aggregate_parent_table,
            ucr_table_query=ucr_query,
            awc_location_table_name='awc_location',
        ), params


class DailyFeedingFormsChildHealthAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'dashboard_child_health_daily_feeding_forms'
    aggregate_parent_table = AGG_DAILY_FEEDING_TABLE
    aggregate_child_table_prefix = 'icds_db_child_daily_feed_form_'

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
          state_id, month, case_id, latest_time_end_processed, sum_attended_child_ids
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            child_health_case_id AS case_id,
            MAX(timeend) AS latest_time_end_processed,
            SUM(attended_child_ids) AS sum_attended_child_ids
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


class AggChildHealthAggregationHelper(BaseICDSAggregationHelper):
    base_tablename = 'agg_child_health'

    def __init__(self, month):
        self.month = transform_day_to_month(month)

    @property
    def child_health_monthly_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.child_health_monthly_ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def _tablename_func(self, agg_level):
        return "{}_{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"), agg_level)

    @property
    def tablename(self):
        return self._tablename_func(5)

    def drop_table_query(self):
        return 'DELETE FROM "{}"'.format(self.tablename)

    def aggregation_query(self):
        columns = (
            ('state_id', 'ucr.state_id'),
            ('district_id', 'ucr.district_id'),
            ('block_id', 'ucr.block_id'),
            ('supervisor_id', 'ucr.supervisor_id'),
            ('awc_id', 'chm.awc_id'),
            ('month', 'chm.month'),
            ('gender', 'chm.sex'),
            ('age_tranche', 'chm.age_tranche'),
            ('caste', 'chm.caste'),
            ('disabled', "COALESCE(chm.disabled, 'no') as coalesce_disabled"),
            ('minority', "COALESCE(chm.minority, 'no') as coalesce_minority"),
            ('resident', "COALESCE(chm.resident, 'no') as coalesce_resident"),
            ('valid_in_month', "SUM(chm.valid_in_month)"),
            ('nutrition_status_weighed', "SUM(chm.nutrition_status_weighed)"),
            ('nutrition_status_unweighed', "SUM(chm.wer_eligible) - SUM(chm.nutrition_status_weighed)"),
            ('nutrition_status_normal',
                "SUM(CASE WHEN ucr.nutrition_status_normal = 1 AND "
                "chm.nutrition_status_weighed = 1 THEN 1 ELSE 0 END)"),
            ('nutrition_status_moderately_underweight',
                "SUM(CASE WHEN ucr.nutrition_status_moderately_underweight = 1 "
                "AND chm.nutrition_status_weighed = 1 THEN 1 ELSE 0 END)"),
            ('nutrition_status_severely_underweight',
                "SUM(CASE WHEN ucr.nutrition_status_severely_underweight = 1 "
                "AND chm.nutrition_status_weighed = 1 THEN 1 ELSE 0 END)"),
            ('wer_eligible', "SUM(chm.wer_eligible)"),
            ('thr_eligible', "SUM(chm.thr_eligible)"),
            ('rations_21_plus_distributed',
                "SUM(CASE WHEN chm.num_rations_distributed >= 21 THEN 1 ELSE 0 END)"),
            ('pse_eligible', "SUM(chm.pse_eligible)"),
            ('pse_attended_16_days',
                "COUNT(*) FILTER (WHERE chm.pse_eligible = 1 AND chm.pse_days_attended >= 16)"),
            ('born_in_month', "SUM(chm.born_in_month)"),
            ('low_birth_weight_in_month', "SUM(chm.low_birth_weight_born_in_month)"),
            ('bf_at_birth', "SUM(chm.bf_at_birth_born_in_month)"),
            ('ebf_eligible', "SUM(chm.ebf_eligible)"),
            ('ebf_in_month', "SUM(chm.ebf_in_month)"),
            ('cf_eligible', "SUM(chm.cf_eligible)"),
            ('cf_in_month', "SUM(chm.cf_in_month)"),
            ('cf_diet_diversity', "SUM(chm.cf_diet_diversity)"),
            ('cf_diet_quantity', "SUM(chm.cf_diet_quantity)"),
            ('cf_demo', "SUM(chm.cf_demo)"),
            ('cf_handwashing', "SUM(chm.cf_handwashing)"),
            ('counsel_increase_food_bf', "SUM(chm.counsel_increase_food_bf)"),
            ('counsel_manage_breast_problems', "SUM(chm.counsel_manage_breast_problems)"),
            ('counsel_ebf', "SUM(chm.counsel_ebf)"),
            ('counsel_adequate_bf', "SUM(chm.counsel_adequate_bf)"),
            ('counsel_pediatric_ifa', "SUM(chm.counsel_pediatric_ifa)"),
            ('counsel_play_cf_video', "SUM(chm.counsel_comp_feeding_vid)"),
            ('fully_immunized_eligible', "SUM(chm.fully_immunized_eligible)"),
            ('fully_immunized_on_time', "SUM(chm.fully_immunized_on_time)"),
            ('fully_immunized_late', "SUM(chm.fully_immunized_late)"),
            ('has_aadhar_id', "SUM(chm.has_aadhar_id)"),
            ('aggregation_level', '5'),
            ('pnc_eligible', 'SUM(chm.pnc_eligible)'),
            # height_eligible calculation is to keep consistent with usage of
            # age_in_months_start & age_in_months_end in UCR
            ('height_eligible',
                "SUM(CASE WHEN chm.age_in_months >= 6 AND chm.age_tranche NOT IN ('72') AND "
                "chm.valid_in_month = 1 THEN 1 ELSE 0 END)"),
            ('wasting_moderate',
                "SUM(CASE WHEN ucr.wasting_moderate = 1 AND ucr.nutrition_status_weighed = 1 "
                "AND ucr.height_measured_in_month = 1 THEN 1 ELSE 0 END)"),
            ('wasting_severe',
                "SUM(CASE WHEN ucr.wasting_severe = 1 AND ucr.nutrition_status_weighed = 1 "
                "AND ucr.height_measured_in_month = 1 THEN 1 ELSE 0 END)"),
            ('stunting_moderate',
                "SUM(CASE WHEN ucr.stunting_moderate = 1 AND ucr.height_measured_in_month = 1 "
                "THEN 1 ELSE 0 END)"),
            ('stunting_severe',
                "SUM(CASE WHEN ucr.stunting_severe = 1 AND ucr.height_measured_in_month = 1 "
                "THEN 1 ELSE 0 END)"),
            ('cf_initiation_in_month', "SUM(chm.cf_initiation_in_month)"),
            ('cf_initiation_eligible', "SUM(chm.cf_initiation_eligible)"),
            ('height_measured_in_month', "SUM(ucr.height_measured_in_month)"),
            ('wasting_normal',
                "SUM(CASE WHEN ucr.wasting_normal = 1 AND ucr.nutrition_status_weighed = 1 "
                "AND ucr.height_measured_in_month = 1 THEN 1 ELSE 0 END)"),
            ('stunting_normal',
                "SUM(CASE WHEN ucr.stunting_normal = 1 AND ucr.height_measured_in_month = 1 "
                "THEN 1 ELSE 0 END)"),
            ('valid_all_registered_in_month', "SUM(chm.valid_all_registered_in_month)"),
            ('ebf_no_info_recorded', "SUM(chm.ebf_no_info_recorded)"),
            ('weighed_and_height_measured_in_month',
                "SUM(CASE WHEN chm.nutrition_status_weighed = 1 AND ucr.height_measured_in_month = 1 "
                "THEN 1 ELSE 0 END)"),
            ('weighed_and_born_in_month',
                "SUM(CASE WHEN (chm.born_in_month = 1 AND (chm.nutrition_status_weighed = 1 "
                "OR chm.low_birth_weight_born_in_month = 1)) THEN 1 ELSE 0 END)"),
            ('zscore_grading_hfa_normal',
                "SUM(CASE WHEN chm.zscore_grading_hfa_recorded_in_month = 1 AND "
                "chm.zscore_grading_hfa = 3 THEN 1 ELSE 0 END)"),
            ('zscore_grading_hfa_moderate',
                "SUM(CASE WHEN chm.zscore_grading_hfa_recorded_in_month = 1 AND "
                "chm.zscore_grading_hfa = 2 THEN 1 ELSE 0 END)"),
            ('zscore_grading_hfa_severe',
                "SUM(CASE WHEN chm.zscore_grading_hfa_recorded_in_month = 1 AND "
                "chm.zscore_grading_hfa = 1 THEN 1 ELSE 0 END)"),
            ('wasting_normal_v2',
                "SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 3 THEN 1 "
                "WHEN chm.muac_grading_recorded_in_month = 1 AND chm.muac_grading = 3 THEN 1 "
                "ELSE 0 END)"),
            ('wasting_moderate_v2',
                "SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 2 THEN 1 "
                "WHEN chm.muac_grading_recorded_in_month = 1 AND chm.muac_grading = 2 THEN 1 "
                "ELSE 0 END)"),
            ('wasting_severe_v2',
                "SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 1 THEN 1 "
                "WHEN chm.muac_grading_recorded_in_month = 1 AND chm.muac_grading = 1 THEN 1 "
                "ELSE 0 END)"),
            ('zscore_grading_hfa_recorded_in_month', "SUM(chm.zscore_grading_hfa_recorded_in_month)"),
            ('zscore_grading_wfh_recorded_in_month', "SUM(chm.zscore_grading_wfh_recorded_in_month)"),
            ('days_ration_given_child', "SUM(chm.days_ration_given_child)"),
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (SELECT
            {calculations}
            FROM "{ucr_child_monthly_table}" ucr
            LEFT OUTER JOIN "{child_health_monthly_table}" chm ON ucr.doc_id = chm.case_id AND ucr.month = chm.month AND ucr.awc_id = chm.awc_id
            WHERE ucr.month = %(start_date)s AND chm.month = %(start_date)s AND
                  ucr.state_id != '' AND ucr.state_id IS NOT NULL
            GROUP BY ucr.state_id, ucr.district_id, ucr.block_id, ucr.supervisor_id, chm.awc_id,
                     chm.month, chm.sex, chm.age_tranche, chm.caste,
                     coalesce_disabled, coalesce_minority, coalesce_resident
            ORDER BY ucr.state_id, ucr.district_id, ucr.block_id, ucr.supervisor_id, chm.awc_id
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            ucr_child_monthly_table=self.child_health_monthly_ucr_tablename,
            child_health_monthly_table='child_health_monthly',
        ), {
            "start_date": self.month
        }

    def rollup_query(self, aggregation_level):
        columns = (
            ('state_id', 'state_id'),
            ('district_id', lambda col: col if aggregation_level > 1 else "'All'"),
            ('block_id', lambda col: col if aggregation_level > 2 else "'All'"),
            ('supervisor_id', lambda col: col if aggregation_level > 3 else "'All'"),
            ('awc_id', lambda col: col if aggregation_level > 4 else "'All'"),
            ('month', 'month'),
            ('gender', 'gender'),
            ('age_tranche', 'age_tranche'),
            ('caste', "'All'"),
            ('disabled', "'All'"),
            ('minority', "'All'"),
            ('resident', "'All'"),
            ('valid_in_month', ),
            ('nutrition_status_weighed', ),
            ('nutrition_status_unweighed', ),
            ('nutrition_status_normal', ),
            ('nutrition_status_moderately_underweight', ),
            ('nutrition_status_severely_underweight', ),
            ('wer_eligible', ),
            ('thr_eligible', ),
            ('rations_21_plus_distributed', ),
            ('pse_eligible', ),
            ('pse_attended_16_days', ),
            ('born_in_month', ),
            ('low_birth_weight_in_month', ),
            ('bf_at_birth', ),
            ('ebf_eligible', ),
            ('ebf_in_month', ),
            ('cf_eligible', ),
            ('cf_in_month', ),
            ('cf_diet_diversity', ),
            ('cf_diet_quantity', ),
            ('cf_demo', ),
            ('cf_handwashing', ),
            ('counsel_increase_food_bf', ),
            ('counsel_manage_breast_problems', ),
            ('counsel_ebf', ),
            ('counsel_adequate_bf', ),
            ('counsel_pediatric_ifa', ),
            ('counsel_play_cf_video', ),
            ('fully_immunized_eligible', ),
            ('fully_immunized_on_time', ),
            ('fully_immunized_late', ),
            ('has_aadhar_id', ),
            ('aggregation_level', str(aggregation_level)),
            ('pnc_eligible', ),
            ('height_eligible', ),
            ('wasting_moderate', ),
            ('wasting_severe', ),
            ('stunting_moderate', ),
            ('stunting_severe', ),
            ('cf_initiation_in_month', ),
            ('cf_initiation_eligible', ),
            ('height_measured_in_month', ),
            ('wasting_normal', ),
            ('stunting_normal', ),
            ('valid_all_registered_in_month', ),
            ('ebf_no_info_recorded', ),
            ('weighed_and_height_measured_in_month', ),
            ('weighed_and_born_in_month', ),
            ('days_ration_given_child', ),
            ('zscore_grading_hfa_normal', ),
            ('zscore_grading_hfa_moderate', ),
            ('zscore_grading_hfa_severe', ),
            ('wasting_normal_v2', ),
            ('wasting_moderate_v2', ),
            ('wasting_severe_v2', ),
            ('zscore_grading_hfa_recorded_in_month', ),
            ('zscore_grading_wfh_recorded_in_month', ),
        )

        def _transform_column(column_tuple):
            column = column_tuple[0]

            if len(column_tuple) == 2:
                agg_col = column_tuple[1]
                if isinstance(agg_col, six.string_types):
                    return column_tuple
                elif callable(agg_col):
                    return (column, agg_col(column))

            return (column, 'SUM({})'.format(column))

        columns = list(map(_transform_column, columns))

        # in the future these may need to include more columns, but historically
        # caste, resident, minority and disabled have been skipped
        group_by = ["state_id", "month", "gender", "age_tranche"]
        if aggregation_level > 1:
            group_by.append("district_id")
        if aggregation_level > 2:
            group_by.append("block_id")
        if aggregation_level > 3:
            group_by.append("supervisor_id")

        return """
        INSERT INTO "{to_tablename}" (
            {columns}
        ) (
            SELECT {calculations}
            FROM "{from_tablename}"
            GROUP BY {group_by}
            ORDER BY {group_by}
        )
        """.format(
            to_tablename=self._tablename_func(aggregation_level),
            from_tablename=self._tablename_func(aggregation_level + 1),
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            group_by=", ".join(group_by),
        )

    def indexes(self, aggregation_level):
        indexes = [
            'CREATE INDEX ON "{}" (state_id)'.format(self.tablename),
            'CREATE INDEX ON "{}" (gender)'.format(self.tablename),
            'CREATE INDEX ON "{}" (age_tranche)'.format(self.tablename),
        ]
        if aggregation_level > 1:
            indexes.append('CREATE INDEX ON "{}" (district_id)'.format(self.tablename))
        if aggregation_level > 2:
            indexes.append('CREATE INDEX ON "{}" (block_id)'.format(self.tablename))
        if aggregation_level > 3:
            indexes.append('CREATE INDEX ON "{}" (supervisor_id)'.format(self.tablename))

        return indexes
