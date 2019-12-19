from custom.icds_reports.utils.aggregation_helpers import get_child_health_temp_tablename
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    AggregationPartitionedHelper,
)


class AggChildHealthAggregationDistributedHelper(AggregationPartitionedHelper):
    helper_key = 'agg-child-health'
    base_tablename = 'agg_child_health'
    staging_tablename = 'staging_agg_child_health'

    @property
    def monthly_tablename(self):
        return "{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"))

    @property
    def previous_agg_table_name(self):
        return f"previous_{self.monthly_tablename}"

    @property
    def model(self):
        from custom.icds_reports.models import AggChildHealth
        return AggChildHealth

    @property
    def child_temp_tablename(self):
        return get_child_health_temp_tablename(self.month)

    @property
    def temporary_tablename(self):
        return 'tmp_agg_child_health_5'

    def staging_queries(self):
        columns = (
            ('state_id', 'awc_loc.state_id'),
            ('district_id', 'awc_loc.district_id'),
            ('block_id', 'awc_loc.block_id'),
            ('supervisor_id', 'chm.supervisor_id'),
            ('awc_id', 'chm.awc_id'),
            ('month', 'chm.month'),
            ('gender', 'chm.sex'),
            ('age_tranche', 'chm.age_tranche'),
            ('caste', 'chm.caste'),
            ('disabled', "COALESCE(chm.disabled, 'no')", "coalesce_disabled"),
            ('minority', "COALESCE(chm.minority, 'no')", "coalesce_minority"),
            ('resident', "COALESCE(chm.resident, 'no')", "coalesce_resident"),
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
            ('pse_attended_21_days',
             "COUNT(*) FILTER (WHERE chm.pse_eligible = 1 AND chm.pse_days_attended >= 21)"),
            ('lunch_count_21_days',
             "COUNT(*) FILTER (WHERE chm.lunch_count >= 21)"),
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
        query_cols = []
        for c in columns:
            if len(c) == 3:
                name = c[2]
            else:
                name = c[0]
            query_cols.append((name, c[1]))

        query_cols = ", ".join([f'{q} as {name}' for name, q in query_cols])
        tmp_tablename = 'blah_blah_blah'
        final_columns = ", ".join([col[0] for col in columns])
        supervisor_id_ranges = [
            ('0', '1'),
            ('1', '2'),
            ('2', '3'),
            ('3', '4'),
            ('4', '5'),
            ('5', '6'),
            ('6', '7'),
            ('7', '8'),
            ('8', '9'),
            ('9', 'A'),
            ('A', 'B'),
            ('B', 'C'),
            ('C', 'D'),
            ('D', 'E'),
            ('E', 'F'),
            ('F', 'zzzzzzzzzz'),
        ]

        return [
            (f"""
            INSERT INTO "{self.temporary_tablename}" ({final_columns})
            SELECT
                {query_cols}
                FROM "{self.child_temp_tablename}" chm
                LEFT OUTER JOIN "awc_location" awc_loc ON (
                    awc_loc.supervisor_id = chm.supervisor_id AND awc_loc.doc_id = chm.awc_id
                )
                WHERE chm.month = %(start_date)s
                      AND awc_loc.state_id != ''
                      AND awc_loc.state_id IS NOT NULL
                      AND chm.supervisor_id >= '{sup_id_begin}'
                      AND chm.supervisor_id < '{sup_id_end}'
                GROUP BY awc_loc.state_id, awc_loc.district_id, awc_loc.block_id, chm.supervisor_id, chm.awc_id,
                         chm.month, chm.sex, chm.age_tranche, chm.caste,
                         coalesce_disabled, coalesce_minority, coalesce_resident;
            """, {
                "start_date": self.month
            })
            for sup_id_begin, sup_id_end in supervisor_id_ranges
        ]

    def update_queries(self):
        yield f"""
            UPDATE "{self.temporary_tablename}" agg SET
              state_is_test = ut.state_is_test,
              district_is_test = ut.district_is_test,
              block_is_test = ut.block_is_test,
              supervisor_is_test = ut.supervisor_is_test,
              awc_is_test = ut.awc_is_test
            FROM (
                SELECT
                    doc_id as awc_id,
                    MAX(state_is_test) as state_is_test,
                    MAX(district_is_test) as district_is_test,
                    MAX(block_is_test) as block_is_test,
                    MAX(supervisor_is_test) as supervisor_is_test,
                    MAX(awc_is_test) as awc_is_test
                FROM "awc_location"
                GROUP BY awc_id, supervisor_id
            ) ut
            WHERE ut.awc_id = agg.awc_id AND (
                (
                  agg.state_is_test IS NULL OR
                  agg.district_is_test IS NULL OR
                  agg.block_is_test IS NULL OR
                  agg.supervisor_is_test IS NULL OR
                  agg.awc_is_test IS NULL
                ) OR (
                  ut.state_is_test != agg.state_is_test OR
                  ut.district_is_test != agg.district_is_test OR
                  ut.block_is_test != agg.block_is_test OR
                  ut.supervisor_is_test != agg.supervisor_is_test OR
                  ut.awc_is_test != agg.awc_is_test
                )
            );
        """, {
        }

        yield f"""
            CREATE TABLE "local_tmp_agg_child_health" AS SELECT * FROM "{self.temporary_tablename}";
            INSERT INTO "{self.staging_tablename}" SELECT * from "local_tmp_agg_child_health";
            DROP TABLE "local_tmp_agg_child_health";
        """, {
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
            ('pse_attended_21_days',),
            ('lunch_count_21_days', ),
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
            ('state_is_test', 'MAX(state_is_test)'),
            (
                'district_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 1 else "0"
            ),
            (
                'block_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 2 else "0"
            ),
            (
                'supervisor_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 3 else "0"
            ),
            (
                'awc_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 4 else "0"
            )
        )

        def _transform_column(column_tuple):
            column = column_tuple[0]

            if len(column_tuple) == 2:
                agg_col = column_tuple[1]
                if isinstance(agg_col, str):
                    return column_tuple
                elif callable(agg_col):
                    return (column, agg_col(column))

            return (column, 'SUM({})'.format(column))

        columns = list(map(_transform_column, columns))

        # in the future these may need to include more columns, but historically
        # caste, resident, minority and disabled have been skipped
        group_by = ["state_id"]
        child_location = 'district_is_test'
        if aggregation_level > 1:
            group_by.append("district_id")
            child_location = 'block_is_test'
        if aggregation_level > 2:
            group_by.append("block_id")
            child_location = 'supervisor_is_test'
        if aggregation_level > 3:
            group_by.append("supervisor_id")
            child_location = 'awc_is_test'

        group_by.extend(["month", "gender", "age_tranche"])
        group_by = ", ".join(group_by)
        column_names = ", ".join([col[0] for col in columns])
        calculations = ", ".join([col[1] for col in columns])

        return f"""
        INSERT INTO "{self.staging_tablename}" (
            {column_names}
        ) (
            SELECT {calculations}
            FROM "{self.staging_tablename}"
            WHERE {child_location} = 0 AND aggregation_level = {aggregation_level + 1}
            GROUP BY {group_by}
            ORDER BY {group_by}
        )
        """

    def indexes(self):
        staging_tablename = self.staging_tablename
        return [
            f'CREATE INDEX ON "{staging_tablename}" (aggregation_level, state_id)',
            f'CREATE INDEX ON "{staging_tablename}" (aggregation_level, gender)',
            f'CREATE INDEX ON "{staging_tablename}" (aggregation_level, age_tranche)',
            f'CREATE INDEX ON "{staging_tablename}" (aggregation_level, district_id) WHERE aggregation_level > 1',
            f'CREATE INDEX ON "{staging_tablename}" (aggregation_level, block_id) WHERE aggregation_level > 2',
            f'CREATE INDEX ON "{staging_tablename}" (aggregation_level, supervisor_id) WHERE aggregation_level > 3',
        ]

    def create_temporary_table(self):
        return """
        CREATE UNLOGGED TABLE \"{table}\" (LIKE agg_child_health INCLUDING INDEXES);
        SELECT create_distributed_table('{table}', 'supervisor_id');
        """.format(table=self.temporary_tablename)

    def drop_temporary_table(self):
        return """
        DROP TABLE IF EXISTS \"{table}\";
        """.format(table=self.temporary_tablename)
