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
    AGG_CCS_RECORD_CF_TABLE,
    AGG_CCS_RECORD_BP_TABLE,
    AGG_CCS_RECORD_PNC_TABLE,
    AGG_CCS_RECORD_THR_TABLE,
    AGG_CCS_RECORD_DELIVERY_TABLE,
    AGG_CHILD_HEALTH_PNC_TABLE,
    AGG_CHILD_HEALTH_THR_TABLE,
    AGG_DAILY_FEEDING_TABLE,
    AGG_GROWTH_MONITORING_TABLE,
    AGG_INFRASTRUCTURE_TABLE,
    AWW_INCENTIVE_TABLE,
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
            ('state_id', 'awc_loc.state_id'),
            ('district_id', 'awc_loc.district_id'),
            ('block_id', 'awc_loc.block_id'),
            ('supervisor_id', 'awc_loc.supervisor_id'),
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
                "SUM(CASE WHEN chm.current_month_nutrition_status = 'normal' THEN 1 ELSE 0 END)"),
            ('nutrition_status_moderately_underweight',
                "SUM(CASE WHEN chm.current_month_nutrition_status = 'moderately_underweight' THEN 1 ELSE 0 END)"),
            ('nutrition_status_severely_underweight',
                "SUM(CASE WHEN chm.current_month_nutrition_status = 'severely_underweight' THEN 1 ELSE 0 END)"),
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
                "SUM(CASE WHEN chm.current_month_wasting = 'moderate' THEN 1 ELSE 0 END)"),
            ('wasting_severe',
                "SUM(CASE WHEN chm.current_month_wasting = 'severe' THEN 1 ELSE 0 END)"),
            ('stunting_moderate',
                "SUM(CASE WHEN chm.current_month_stunting = 'moderate' THEN 1 ELSE 0 END)"),
            ('stunting_severe',
                "SUM(CASE WHEN chm.current_month_stunting = 'severe' THEN 1 ELSE 0 END)"),
            ('cf_initiation_in_month', "SUM(chm.cf_initiation_in_month)"),
            ('cf_initiation_eligible', "SUM(chm.cf_initiation_eligible)"),
            ('height_measured_in_month', "SUM(chm.height_measured_in_month)"),
            ('wasting_normal',
                "SUM(CASE WHEN chm.current_month_wasting = 'normal' THEN 1 ELSE 0 END)"),
            ('stunting_normal',
                "SUM(CASE WHEN chm.current_month_stunting = 'normal' THEN 1 ELSE 0 END)"),
            ('valid_all_registered_in_month', "SUM(chm.valid_all_registered_in_month)"),
            ('ebf_no_info_recorded', "SUM(chm.ebf_no_info_recorded)"),
            ('weighed_and_height_measured_in_month',
                "SUM(CASE WHEN chm.nutrition_status_weighed = 1 AND chm.height_measured_in_month = 1 "
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
                "ELSE 0 END)"),
            ('wasting_moderate_v2',
                "SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 2 THEN 1 "
                "ELSE 0 END)"),
            ('wasting_severe_v2',
                "SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 1 THEN 1 "
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
            FROM "{child_health_monthly_table}" chm
            LEFT OUTER JOIN "awc_location" awc_loc ON awc_loc.doc_id = chm.awc_id
            WHERE chm.month = %(start_date)s AND awc_loc.state_id != '' AND awc_loc.state_id IS NOT NULL
            GROUP BY awc_loc.state_id, awc_loc.district_id, awc_loc.block_id, awc_loc.supervisor_id, chm.awc_id,
                     chm.month, chm.sex, chm.age_tranche, chm.caste,
                     coalesce_disabled, coalesce_minority, coalesce_resident
            ORDER BY awc_loc.state_id, awc_loc.district_id, awc_loc.block_id, awc_loc.supervisor_id, chm.awc_id
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
        group_by = ["state_id"]
        if aggregation_level > 1:
            group_by.append("district_id")
        if aggregation_level > 2:
            group_by.append("block_id")
        if aggregation_level > 3:
            group_by.append("supervisor_id")

        group_by.extend(["month", "gender", "age_tranche"])

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


class CcsRecordMonthlyAggregationHelper(BaseICDSAggregationHelper):
    base_tablename = 'ccs_record_monthly'

    def __init__(self, month):
        self.month = transform_day_to_month(month)
        self.end_date = transform_day_to_month(month + relativedelta(months=1, seconds=-1))

    @property
    def ccs_record_monthly_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ccs_record_monthly_ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def ccs_record_case_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-ccs_record_cases')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def pregnant_tasks_cases_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-pregnant-tasks_cases')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def tablename(self):
        return "{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"))

    def drop_table_query(self):
        return 'DELETE FROM "{}"'.format(self.tablename)

    def aggregation_query(self):

        columns = (
            ('awc_id', 'ucr.awc_id'),
            ('case_id', 'ucr.case_id'),
            ('month', 'ucr.month'),
            ('age_in_months', 'ucr.age_in_months'),
            ('ccs_status', 'ucr.ccs_status'),
            ('open_in_month', 'ucr.open_in_month'),
            ('alive_in_month', 'ucr.alive_in_month'),
            ('trimester', 'ucr.trimester'),
            ('num_rations_distributed', 'COALESCE(agg_thr.days_ration_given_mother, 0)'),
            ('thr_eligible', 'ucr.thr_eligible'),
            ('tetanus_complete', 'ucr.tetanus_complete'),
            ('delivered_in_month', 'ucr.delivered_in_month'),
            ('anc1_received_at_delivery', 'ucr.anc1_received_at_delivery'),
            ('anc2_received_at_delivery', 'ucr.anc2_received_at_delivery'),
            ('anc3_received_at_delivery', 'ucr.anc3_received_at_delivery'),
            ('anc4_received_at_delivery', 'ucr.anc4_received_at_delivery'),
            ('registration_trimester_at_delivery', 'ucr.registration_trimester_at_delivery'),
            ('using_ifa', 'ucr.using_ifa'),
            ('ifa_consumed_last_seven_days', 'ucr.ifa_consumed_last_seven_days'),
            ('anemic_severe', 'ucr.anemic_severe'),
            ('anemic_moderate', 'ucr.anemic_moderate'),
            ('anemic_normal', 'ucr.anemic_normal'),
            ('anemic_unknown', 'ucr.anemic_unknown'),
            ('extra_meal', 'ucr.extra_meal'),
            ('resting_during_pregnancy', 'ucr.resting_during_pregnancy'),
            ('bp_visited_in_month', 'ucr.bp_visited_in_month'),
            ('pnc_visited_in_month', 'NULL'),
            ('trimester_2', 'ucr.trimester_2'),
            ('trimester_3', 'ucr.trimester_3'),
            ('counsel_immediate_bf', 'ucr.counsel_immediate_bf'),
            ('counsel_bp_vid', 'ucr.counsel_bp_vid'),
            ('counsel_preparation', 'ucr.counsel_preparation'),
            ('counsel_fp_vid', 'ucr.counsel_fp_vid'),
            ('counsel_immediate_conception', 'ucr.counsel_immediate_conception'),
            ('counsel_accessible_postpartum_fp', 'ucr.counsel_accessible_postpartum_fp'),
            ('bp1_complete', 'ucr.bp1_complete'),
            ('bp2_complete', 'ucr.bp2_complete'),
            ('bp3_complete', 'ucr.bp3_complete'),
            ('pnc_complete', 'ucr.pnc_complete'),
            ('postnatal', 'ucr.postnatal'),
            ('has_aadhar_id', 'ucr.has_aadhar_id'),
            ('counsel_fp_methods', 'NULL'),
            ('pregnant', 'ucr.pregnant'),
            ('pregnant_all', 'ucr.pregnant_all'),
            ('lactating', 'ucr.lactating'),
            ('lactating_all', 'ucr.lactating_all'),
            ('institutional_delivery_in_month', 'ucr.institutional_delivery_in_month'),
            ('add', 'ucr.add'),
            ('caste', 'ucr.caste'),
            ('disabled', 'ucr.disabled'),
            ('minority', 'ucr.minority'),
            ('resident', 'ucr.resident'),
            ('valid_in_month', 'ucr.valid_in_month'),
            ('anc_in_month',
             '( '
                '(CASE WHEN ut.due_list_date_anc_1 BETWEEN %(start_date)s AND %(end_date)s THEN 1 ELSE 0 END) + '
                '(CASE WHEN ut.due_list_date_anc_2 BETWEEN %(start_date)s AND %(end_date)s THEN 1 ELSE 0 END) + '
                '(CASE WHEN ut.due_list_date_anc_3 BETWEEN %(start_date)s AND %(end_date)s THEN 1 ELSE 0 END) + '
                '(CASE WHEN ut.due_list_date_anc_4 BETWEEN %(start_date)s AND %(end_date)s THEN 1 ELSE 0 END) '
                ')'),
            ('anc_1', 'ut.due_list_date_anc_1'),
            ('anc_2', 'ut.due_list_date_anc_2'),
            ('anc_3', 'ut.due_list_date_anc_3'),
            ('anc_4', 'ut.due_list_date_anc_4'),
            ('tt_1', 'ut.due_list_date_tt_1'),
            ('tt_2', 'ut.due_list_date_tt_2'),
            ('immediate_breastfeeding', 'agg_bp.immediate_breastfeeding'),
            ('anemia', 'agg_bp.anemia'),
            ('eating_extra', 'agg_bp.eating_extra'),
            ('resting', 'agg_bp.resting'),
            ('anc_weight', 'agg_bp.anc_weight'),
            ('anc_blood_pressure', 'agg_bp.anc_blood_pressure'),
            ('bp_sys', 'agg_bp.bp_sys'),
            ('bp_dia', 'agg_bp.bp_dia'),
            ('anc_hemoglobin', 'agg_bp.anc_hemoglobin'),
            ('bleeding', 'agg_bp.bleeding'),
            ('swelling', 'agg_bp.swelling'),
            ('blurred_vision', 'agg_bp.blurred_vision'),
            ('convulsions', 'agg_bp.convulsions'),
            ('rupture', 'agg_bp.rupture'),
            ('bp_date', 'agg_bp.latest_time_end_processed::DATE'),
            ('is_ebf', 'agg_pnc.is_ebf'),
            ('breastfed_at_birth', 'agg_delivery.breastfed_at_birth'),
            ('person_name', 'case_list.person_name'),
            ('edd', 'case_list.edd'),
            ('delivery_nature', 'case_list.delivery_nature'),
            ('mobile_number', 'case_list.mobile_number'),
            ('preg_order', 'case_list.preg_order'),
            ('num_pnc_visits', 'case_list.num_pnc_visits'),
            ('last_date_thr', 'case_list.last_date_thr'),
            ('num_anc_complete', 'case_list.num_anc_complete'),
            ('valid_visits', 'agg_cf.valid_visits + agg_bp.valid_visits + agg_pnc.valid_visits'),
            ('opened_on', 'case_list.opened_on'),
            ('dob', 'case_list.dob')
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (SELECT
            {calculations}
            FROM "{ucr_ccs_record_monthly_table}" ucr
            LEFT OUTER JOIN "{agg_thr_table}" agg_thr ON ucr.doc_id = agg_thr.case_id AND ucr.month = agg_thr.month and ucr.valid_in_month = 1
            LEFT OUTER JOIN "{agg_bp_table}" agg_bp ON ucr.doc_id = agg_bp.case_id AND ucr.month = agg_bp.month and ucr.valid_in_month = 1
            LEFT OUTER JOIN "{agg_pnc_table}" agg_pnc ON ucr.doc_id = agg_pnc.case_id AND ucr.month = agg_pnc.month and ucr.valid_in_month = 1
            LEFT OUTER JOIN "{agg_cf_table}" agg_cf ON ucr.doc_id = agg_cf.case_id AND ucr.month = agg_cf.month and ucr.valid_in_month = 1
            LEFT OUTER JOIN "{agg_delivery_table}" agg_delivery ON ucr.doc_id = agg_delivery.case_id AND ucr.month = agg_delivery.month and ucr.valid_in_month = 1
            LEFT OUTER JOIN "{ccs_record_case_ucr}" case_list ON ucr.doc_id = case_list.doc_id
            LEFT OUTER JOIN "{pregnant_tasks_case_ucr}" ut ON ucr.doc_id = ut.ccs_record_case_id
            WHERE ucr.month = %(start_date)s
            ORDER BY ucr.awc_id, ucr.case_id
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            ucr_ccs_record_monthly_table=self.ccs_record_monthly_ucr_tablename,
            agg_thr_table=AGG_CCS_RECORD_THR_TABLE,
            ccs_record_case_ucr=self.ccs_record_case_ucr_tablename,
            agg_pnc_table=AGG_CCS_RECORD_PNC_TABLE,
            agg_bp_table=AGG_CCS_RECORD_BP_TABLE,
            agg_delivery_table=AGG_CCS_RECORD_DELIVERY_TABLE,
            pregnant_tasks_case_ucr=self.pregnant_tasks_cases_ucr_tablename,
            agg_cf_table=AGG_CCS_RECORD_CF_TABLE,
        ), {
            "start_date": self.month,
            "end_date": self.end_date
        }

    def indexes(self):
        return [
            'CREATE INDEX ON "{}" (awc_id, case_id)'.format(self.tablename),
        ]


class AggCcsRecordAggregationHelper(BaseICDSAggregationHelper):
    base_tablename = 'agg_ccs_record'

    def __init__(self, month):
        self.month = transform_day_to_month(month)

    @property
    def ccs_record_monthly_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ccs_record_monthly_ucr_id)
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
            ('state_id', 'state_id'),
            ('district_id', 'district_id'),
            ('block_id', 'block_id'),
            ('supervisor_id', 'supervisor_id'),
            ('awc_id', 'ucr.awc_id'),
            ('month', 'ucr.month'),
            ('ccs_status', 'ucr.ccs_status'),
            ('trimester', "COALESCE(ucr.trimester::text, '') as coalesce_trimester"),
            ('caste', 'ucr.caste'),
            ('disabled', "COALESCE(ucr.disabled, 'no') as coalesce_disabled"),
            ('minority', "COALESCE(ucr.minority, 'no') as coalesce_minority"),
            ('resident', "COALESCE(ucr.resident,'no') as coalesce_resident"),
            ('valid_in_month', 'sum(ucr.valid_in_month)'),
            ('lactating', 'sum(ucr.lactating)'),
            ('pregnant', 'sum(ucr.pregnant)'),
            ('thr_eligible', 'sum(ucr.thr_eligible)'),
            ('rations_21_plus_distributed', 'sum(ucr.rations_21_plus_distributed)'),
            ('tetanus_complete', 'sum(ucr.tetanus_complete)'),
            ('delivered_in_month', 'sum(ucr.delivered_in_month)'),
            ('anc1_received_at_delivery', 'sum(ucr.anc1_received_at_delivery)'),
            ('anc2_received_at_delivery', 'sum(ucr.anc2_received_at_delivery)'),
            ('anc3_received_at_delivery', 'sum(ucr.anc3_received_at_delivery)'),
            ('anc4_received_at_delivery', 'sum(ucr.anc4_received_at_delivery)'),
            ('registration_trimester_at_delivery', 'avg(ucr.registration_trimester_at_delivery)'),
            ('using_ifa', 'sum(ucr.using_ifa)'),
            ('ifa_consumed_last_seven_days', 'sum(ucr.ifa_consumed_last_seven_days)'),
            ('anemic_normal', 'sum(ucr.anemic_normal)'),
            ('anemic_moderate', 'sum(ucr.anemic_moderate)'),
            ('anemic_severe', 'sum(ucr.anemic_severe)'),
            ('anemic_unknown', 'sum(ucr.anemic_unknown)'),
            ('extra_meal', 'sum(ucr.extra_meal)'),
            ('resting_during_pregnancy', 'sum(ucr.resting_during_pregnancy)'),
            ('bp1_complete', 'sum(ucr.bp1_complete)'),
            ('bp2_complete', 'sum(ucr.bp2_complete)'),
            ('bp3_complete', 'sum(ucr.bp3_complete)'),
            ('pnc_complete', 'sum(ucr.pnc_complete)'),
            ('trimester_2', 'sum(ucr.trimester_2)'),
            ('trimester_3', 'sum(ucr.trimester_3)'),
            ('postnatal', 'sum(ucr.postnatal)'),
            ('counsel_bp_vid', 'sum(ucr.counsel_bp_vid)'),
            ('counsel_preparation', 'sum(ucr.counsel_preparation)'),
            ('counsel_immediate_bf', 'sum(ucr.counsel_immediate_bf)'),
            ('counsel_fp_vid', 'sum(ucr.counsel_fp_vid)'),
            ('counsel_immediate_conception', 'sum(ucr.counsel_immediate_conception)'),
            ('counsel_accessible_postpartum_fp', 'sum(ucr.counsel_accessible_postpartum_fp)'),
            ('has_aadhar_id', 'sum(ucr.has_aadhar_id)'),
            ('aggregation_level', '5 '),
            ('valid_all_registered_in_month', 'sum(ucr.valid_all_registered_in_month)'),
            ('institutional_delivery_in_month', 'sum(ucr.institutional_delivery_in_month)'),
            ('lactating_all', 'sum(ucr.lactating_all)'),
            ('pregnant_all', 'sum(ucr.pregnant_all)'),
            ('valid_visits', 'sum(crm.valid_visits)'),
            ('expected_visits', 'floor(sum( '
             'CASE '
             'WHEN ucr.pregnant=1 THEN 0.44 '
             'WHEN ucr.month - ucr.add < 0 THEN 6 '
             'WHEN ucr.month - ucr.add < 182 THEN 1 '
             'ELSE 0.39 END'
             '))'),
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (SELECT
            {calculations}
            FROM "{ucr_ccs_record_table}" ucr
            LEFT OUTER JOIN "{ccs_record_monthly_table}" as crm
            ON crm.case_id = ucr.doc_id and crm.month=ucr.month
            WHERE ucr.month = %(start_date)s AND state_id != ''
            GROUP BY state_id, district_id, block_id, supervisor_id, ucr.awc_id, ucr.month,
                     ucr.ccs_status, coalesce_trimester, ucr.caste, coalesce_disabled, coalesce_minority, coalesce_resident
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            ucr_ccs_record_table=self.ccs_record_monthly_ucr_tablename,
            ccs_record_monthly_table='ccs_record_monthly'
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
            ('ccs_status', 'ccs_status'),
            ('trimester', "'All'"),
            ('caste', "'All'"),
            ('disabled', "'All'"),
            ('minority', "'All'"),
            ('resident', "'All'"),
            ('valid_in_month', ),
            ('lactating', ),
            ('pregnant', ),
            ('thr_eligible', ),
            ('rations_21_plus_distributed', ),
            ('tetanus_complete', ),
            ('delivered_in_month', ),
            ('anc1_received_at_delivery', ),
            ('anc2_received_at_delivery', ),
            ('anc3_received_at_delivery', ),
            ('anc4_received_at_delivery', ),
            ('registration_trimester_at_delivery', 'AVG(registration_trimester_at_delivery)'),
            ('using_ifa', ),
            ('ifa_consumed_last_seven_days', ),
            ('anemic_normal', ),
            ('anemic_moderate', ),
            ('anemic_severe', ),
            ('anemic_unknown', ),
            ('extra_meal', ),
            ('resting_during_pregnancy', ),
            ('bp1_complete', ),
            ('bp2_complete', ),
            ('bp3_complete', ),
            ('pnc_complete', ),
            ('trimester_2', ),
            ('trimester_3', ),
            ('postnatal', ),
            ('counsel_bp_vid', ),
            ('counsel_preparation', ),
            ('counsel_immediate_bf', ),
            ('counsel_fp_vid', ),
            ('counsel_immediate_conception', ),
            ('counsel_accessible_postpartum_fp', ),
            ('has_aadhar_id', ),
            ('aggregation_level', str(aggregation_level)),
            ('valid_all_registered_in_month', ),
            ('institutional_delivery_in_month', ),
            ('lactating_all', ),
            ('pregnant_all', ),
            ('valid_visits', ),
            ('expected_visits', ),
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
        group_by = ["state_id", "month", "ccs_status"]
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
            'CREATE INDEX ON "{}" (ccs_status)'.format(self.tablename),
        ]

        agg_locations = ['state_id']
        if aggregation_level > 1:
            indexes.append('CREATE INDEX ON "{}" (district_id)'.format(self.tablename))
            agg_locations.append('district_id')
        if aggregation_level > 2:
            indexes.append('CREATE INDEX ON "{}" (block_id)'.format(self.tablename))
            agg_locations.append('block_id')
        if aggregation_level > 3:
            indexes.append('CREATE INDEX ON "{}" (supervisor_id)'.format(self.tablename))
            agg_locations.append('supervisor_id')

        indexes.append('CREATE INDEX ON "{}" ({})'.format(self.tablename, ', '.join(agg_locations)))
        return indexes


class AwcInfrastructureAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-infrastructure_form_v2'
    aggregate_parent_table = AGG_INFRASTRUCTURE_TABLE
    aggregate_child_table_prefix = 'icds_db_infra_form_'
    column_names = (
        'timeend',
        'awc_building', 'source_drinking_water', 'toilet_functional',
        'electricity_awc', 'adequate_space_pse',
        'adult_scale_available', 'baby_scale_available', 'flat_scale_available',
        'adult_scale_usable', 'baby_scale_usable', 'cooking_utensils_usable',
        'infantometer_usable', 'medicine_kits_usable', 'stadiometer_usable',
    )

    def _window_helper(self, column_name):
        return (
            "LAST_VALUE({column}) OVER {column} AS {column}".format(column=column_name),
            """
            {column} AS (
                PARTITION BY awc_id
                ORDER BY
                    CASE WHEN {column} IS NULL THEN 0 ELSE 1 END ASC,
                    timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
            """.format(column=column_name)
        )

    def data_from_ucr_query(self):
        next_month_start = month_formatter(self.month + relativedelta(months=1))
        six_months_ago = month_formatter(self.month - relativedelta(months=6))

        windows = [
            self._window_helper(column_name)
            for column_name in self.column_names
        ]
        select_lines = ', '.join([window[0] for window in windows])
        window_lines = ', '.join([window[1] for window in windows])

        return """
            SELECT
                DISTINCT awc_id AS awc_id,
                {select_lines}
            FROM "{ucr_tablename}"
            WHERE timeend >= %(six_months_ago)s AND timeend < %(next_month_start)s
                AND state_id = %(state_id)s AND awc_id IS NOT NULL
            WINDOW
                {window_lines}
        """.format(
            ucr_tablename=self.ucr_tablename,
            select_lines=select_lines,
            window_lines=window_lines,
        ), {
            "six_months_ago": six_months_ago,
            "next_month_start": next_month_start,
            "state_id": self.state_id,
        }

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)

        ucr_query, ucr_query_params = self.data_from_ucr_query()
        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id
        }
        query_params.update(ucr_query_params)

        return """
        INSERT INTO "{tablename}" (
            state_id, month, awc_id, latest_time_end_processed,
            awc_building, source_drinking_water, toilet_functional,
            electricity_awc, adequate_space_pse,
            adult_scale_available, baby_scale_available, flat_scale_available,
            adult_scale_usable, baby_scale_usable, cooking_utensils_usable,
            infantometer_usable, medicine_kits_usable, stadiometer_usable
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            ucr.awc_id AS awc_id,
            ucr.timeend as latest_time_end_processed,
            ucr.awc_building as awc_building,
            ucr.source_drinking_water as source_drinking_water,
            ucr.toilet_functional as toilet_functional,
            ucr.electricity_awc as electricity_awc,
            ucr.adequate_space_pse as adequate_space_pse,
            ucr.adult_scale_available as adult_scale_available,
            ucr.baby_scale_available as baby_scale_available,
            ucr.flat_scale_available as flat_scale_available,
            ucr.adult_scale_usable as adult_scale_usable,
            ucr.baby_scale_usable as baby_scale_usable,
            ucr.cooking_utensils_usable as cooking_utensils_usable,
            ucr.infantometer_usable as infantometer_usable,
            ucr.medicine_kits_usable as medicine_kits_usable,
            ucr.stadiometer_usable as stadiometer_usable
          FROM ({ucr_table_query}) ucr
        )
        """.format(
            ucr_table_query=ucr_query,
            tablename=tablename
        ), query_params


class AwwIncentiveAggregationHelper(BaseICDSAggregationHelper):
    aggregate_parent_table = AWW_INCENTIVE_TABLE
    aggregate_child_table_prefix = 'icds_db_aww_incentive_'

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)

        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id
        }

        return """
        INSERT INTO "{tablename}" (
            state_id, month, awc_id, block_id, state_name, district_name, block_name, 
            supervisor_name, awc_name, aww_name, contact_phone_number, wer_weighed,
            wer_eligible, awc_num_open, valid_visits, expected_visits
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            awc_id,
            block_id,
            state_name,
            district_name,
            block_name,
            supervisor_name,
            awc_name,
            aww_name,
            contact_phone_number,
            wer_weighed,
            wer_eligible,
            awc_num_open,
            valid_visits,
            expected_visits
          FROM agg_ccs_record_monthly AS acm
          WHERE acm.month = %(month)s AND acm.state_id = %(state_id)s and aggregation_level=5
        )
        """.format(
            tablename=tablename
        ), query_params
