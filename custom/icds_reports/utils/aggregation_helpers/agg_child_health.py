from __future__ import absolute_import
from __future__ import unicode_literals

import six

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from six.moves import map

from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, transform_day_to_month


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
