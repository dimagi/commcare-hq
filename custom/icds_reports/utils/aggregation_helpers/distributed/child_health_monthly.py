from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import (
    AGG_COMP_FEEDING_TABLE,
    AGG_CHILD_HEALTH_PNC_TABLE,
    AGG_CHILD_HEALTH_THR_TABLE,
    AGG_DAILY_FEEDING_TABLE,
    AGG_GROWTH_MONITORING_TABLE,
)
from custom.icds_reports.utils.aggregation_helpers import transform_day_to_month, month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper


class ChildHealthMonthlyAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    """This helper differs from the others in the following ways:

    * It must insert into a temporary table before inserting into the final table
    * It takes in multiple state_ids instead of one state_id
    * It provides one aggregation query per state_id passed in

    Future work:
    * Partition the child_health_monthly table (may be done in citus work).
      This would make it much easier to make it like other helpers
    """

    helper_key = 'child-health-monthly'
    base_tablename = 'child_health_monthly'

    def __init__(self, state_ids, month):
        self.state_ids = state_ids
        self.month = transform_day_to_month(month)

    def aggregate(self, cursor):
        drop_query, drop_params = self.drop_table_query()

        cursor.execute(drop_query, drop_params)
        cursor.execute(self.aggregation_query())
        for query in self.indexes():
            cursor.execute(query)

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
    def person_case_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-person_cases_v3')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def tablename(self):
        return self.base_tablename

    @property
    def temporary_tablename(self):
        return "tmp_{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"))

    def drop_table_query(self):
        return 'DELETE FROM "{}" WHERE month=%(month)s'.format(self.tablename), {'month': self.month}

    def _state_aggregation_query(self, state_id):
        start_month_string = self.month.strftime("'%Y-%m-%d'::date")
        end_month_string = (self.month + relativedelta(months=1, days=-1)).strftime("'%Y-%m-%d'::date")
        age_in_days = "({} - person_cases.dob)::integer".format(end_month_string)
        age_in_months_end = "({} / 30.4 )".format(age_in_days)
        age_in_months = "(({} - person_cases.dob) / 30.4 )".format(start_month_string)
        open_in_month = (
            "(({} - child_health.opened_on::date)::integer >= 0) "
            "AND (child_health.closed = 0 OR (child_health.closed_on::date - {})::integer > 0)"
        ).format(end_month_string, start_month_string)
        alive_in_month = "(child_health.date_death IS NULL OR child_health.date_death - {} >= 0)".format(
            start_month_string
        )
        seeking_services = "(child_health.is_availing = 1 AND child_health.is_migrated = 0)"
        born_in_month = "({} AND person_cases.dob BETWEEN {} AND {})".format(
            seeking_services, start_month_string, end_month_string
        )
        valid_in_month = "({} AND {} AND {} AND {} <= 72)".format(
            open_in_month, alive_in_month, seeking_services, age_in_months
        )
        pse_eligible = "({} AND {} > 36)".format(valid_in_month, age_in_months_end)
        ebf_eligible = "({} AND {} <= 6)".format(valid_in_month, age_in_months)
        wer_eligible = "({} AND {} <= 60)".format(valid_in_month, age_in_months)
        cf_eligible = "({} AND {} > 6 AND {} <= 24)".format(valid_in_month, age_in_months_end, age_in_months)
        cf_initiation_eligible = "({} AND {} > 6 AND {} <= 8)".format(
            valid_in_month, age_in_months_end, age_in_months
        )
        thr_eligible = "({} AND {} > 6 AND {} <= 36)".format(valid_in_month, age_in_months_end, age_in_months)
        pnc_eligible = "({} AND {} - person_cases.dob > 0 AND {} - person_cases.dob <= 20)".format(
            valid_in_month, end_month_string, start_month_string
        )
        height_eligible = "({} AND {} > 6 AND {} <= 60)".format(valid_in_month, age_in_months_end, age_in_months)
        fully_immunized_eligible = "({} AND {} > 12)".format(valid_in_month, age_in_months_end)
        immunized_age_in_days = "(child_tasks.immun_one_year_date - person_cases.dob)"
        fully_immun_before_month = "(child_tasks.immun_one_year_date < {})".format(end_month_string)

        columns = (
            ("awc_id", "child_health.awc_id"),
            ("case_id", "child_health.doc_id"),
            ("supervisor_id", "child_health.supervisor_id"),
            ("month", self.month.strftime("'%Y-%m-%d'")),
            ("sex", "child_health.sex"),
            ("age_tranche",
                "CASE WHEN {age_in_days} <= 28 THEN 0 "
                "     WHEN {age_in_months} <= 6 THEN 6 "
                "     WHEN {age_in_months} <= 12 THEN 12 "
                "     WHEN {age_in_months} <= 24 THEN 24 "
                "     WHEN {age_in_months} <= 36 THEN 36 "
                "     WHEN {age_in_months} <= 48 THEN 48 "
                "     WHEN {age_in_months} <= 60 THEN 60 "
                "     WHEN {age_in_months} <= 72 THEN 72 "
                "ELSE NULL END".format(age_in_days=age_in_days, age_in_months=age_in_months)),
            ("caste", "child_health.caste"),
            ("disabled", "child_health.disabled"),
            ("minority", "child_health.minority"),
            ("resident", "child_health.resident"),
            ("dob", "person_cases.dob"),
            ("age_in_months", 'trunc({})'.format(age_in_months_end)),
            ("open_in_month", "CASE WHEN {} THEN 1 ELSE 0 END".format(open_in_month)),
            ("alive_in_month", "CASE WHEN {} THEN 1 ELSE 0 END".format(alive_in_month)),
            ("born_in_month", "CASE WHEN {} THEN 1 ELSE 0 END".format(born_in_month)),
            ("bf_at_birth_born_in_month",
                "CASE WHEN {} AND child_health.bf_at_birth = 'yes' THEN 1 ELSE 0 END".format(born_in_month)),
            ("low_birth_weight_born_in_month",
                "CASE WHEN {} AND child_health.lbw_open_count = 1 THEN 1 ELSE 0 END".format(born_in_month)),
            ("fully_immunized_eligible", "CASE WHEN {} THEN 1 ELSE 0 END".format(fully_immunized_eligible)),
            ("fully_immunized_on_time", "CASE WHEN {} AND {} <= 365 AND {} THEN 1 ELSE 0 END".format(
                fully_immunized_eligible, immunized_age_in_days, fully_immun_before_month
            )),
            ("fully_immunized_late", "CASE WHEN {} AND {} > 365 AND {} THEN 1 ELSE 0 END".format(
                fully_immunized_eligible, immunized_age_in_days, fully_immun_before_month
            )),
            ("has_aadhar_id",
                "CASE WHEN person_cases.aadhar_date < {} THEN  1 ELSE 0 END".format(end_month_string)),
            ("valid_in_month", "CASE WHEN {} THEN 1 ELSE 0 END".format(valid_in_month)),
            ("valid_all_registered_in_month",
                "CASE WHEN {} AND {} AND {} <= 72 AND child_health.is_migrated = 0 THEN 1 ELSE 0 END".format(
                    open_in_month, alive_in_month, age_in_months
            )),
            ("person_name", "child_health.person_name"),
            ("mother_name", "child_health.mother_name"),
            # PSE/DF Indicators
            ("pse_eligible", "CASE WHEN {} THEN 1 ELSE 0 END".format(pse_eligible)),
            ("pse_days_attended",
                "CASE WHEN {} THEN COALESCE(df.sum_attended_child_ids, 0) ELSE NULL END".format(pse_eligible)),
            ("lunch_count", "COALESCE(df.lunch_count, 0)"),
            # EBF Indicators
            ("ebf_eligible", "CASE WHEN {} THEN 1 ELSE 0 END".format(ebf_eligible)),
            ("ebf_in_month", "CASE WHEN {} THEN COALESCE(pnc.is_ebf, 0) ELSE 0 END".format(ebf_eligible)),
            ("ebf_not_breastfeeding_reason",
                "CASE WHEN {} THEN pnc.not_breastfeeding ELSE NULL END".format(ebf_eligible)),
            ("ebf_drinking_liquid",
                "CASE WHEN {} THEN GREATEST(pnc.water_or_milk, pnc.other_milk_to_child, pnc.tea_other, 0) "
                "ELSE 0 END".format(ebf_eligible)),
            ("ebf_eating",
                "CASE WHEN {} THEN COALESCE(pnc.eating, 0) ELSE 0 END".format(ebf_eligible)),
            ("ebf_no_bf_no_milk", "0"),
            ("ebf_no_bf_pregnant_again", "0"),
            ("ebf_no_bf_child_too_old", "0"),
            ("ebf_no_bf_mother_sick", "0"),
            ("counsel_adequate_bf",
                "CASE WHEN {} THEN COALESCE(pnc.counsel_adequate_bf, 0) ELSE 0 END".format(ebf_eligible)),
            ("ebf_no_info_recorded",
                "CASE WHEN {} AND date_trunc('MONTH', pnc.latest_time_end_processed) = %(start_date)s "
                "THEN 0 ELSE (CASE WHEN {} THEN 1 ELSE 0 END) END".format(ebf_eligible, ebf_eligible)),
            ("counsel_ebf",
                "CASE WHEN {} THEN GREATEST(pnc.counsel_exclusive_bf, pnc.counsel_only_milk, 0) "
                "ELSE 0 END".format(ebf_eligible)),
            # PNC Indicators
            ("pnc_eligible", "CASE WHEN {} THEN 1 ELSE 0 END".format(pnc_eligible)),
            ("counsel_increase_food_bf",
                "CASE WHEN {} THEN COALESCE(pnc.counsel_increase_food_bf, 0) ELSE 0 END".format(pnc_eligible)),
            ("counsel_manage_breast_problems",
                "CASE WHEN {} THEN COALESCE(pnc.counsel_breast, 0) ELSE 0 END".format(pnc_eligible)),
            ("counsel_skin_to_skin",
                "CASE WHEN {} THEN COALESCE(pnc.skin_to_skin, 0) ELSE 0 END".format(pnc_eligible)),
            # GM Indicators
            ("wer_eligible", "CASE WHEN {} THEN 1 ELSE 0 END".format(wer_eligible)),
            ("nutrition_status_last_recorded",
                "CASE "
                "WHEN NOT {} THEN NULL "
                "WHEN gm.zscore_grading_wfa = 1 THEN 'severely_underweight' "
                "WHEN gm.zscore_grading_wfa = 2 THEN 'moderately_underweight' "
                "WHEN gm.zscore_grading_wfa IN (3, 4) THEN 'normal' "
                "ELSE 'unknown' END".format(wer_eligible)),
            ("current_month_nutrition_status",
                "CASE "
                "WHEN NOT {} THEN NULL "
                "WHEN date_trunc('MONTH', gm.zscore_grading_wfa_last_recorded) != %(start_date)s THEN 'unweighed' "
                "WHEN gm.zscore_grading_wfa = 1 THEN 'severely_underweight' "
                "WHEN gm.zscore_grading_wfa = 2 THEN 'moderately_underweight' "
                "WHEN gm.zscore_grading_wfa IN (3, 4) THEN 'normal' "
                "ELSE 'unweighed' END".format(wer_eligible)),
            ("nutrition_status_weighed",
                "CASE "
                "WHEN {} AND date_trunc('MONTH', gm.zscore_grading_wfa_last_recorded) = %(start_date)s THEN 1 "
                "ELSE 0 END".format(wer_eligible)),
            ("recorded_weight",
                "CASE "
                "WHEN NOT {} THEN NULL "
                "WHEN date_trunc('MONTH', gm.weight_child_last_recorded) = %(start_date)s THEN gm.weight_child "
                "ELSE NULL END".format(wer_eligible)),
            ("recorded_height",
                "CASE "
                "WHEN date_trunc('MONTH', gm.height_child_last_recorded) = %(start_date)s THEN gm.height_child "
                "ELSE NULL END"),
            ("height_measured_in_month",
                "CASE "
                "WHEN date_trunc('MONTH', gm.height_child_last_recorded) = %(start_date)s AND {} THEN 1 "
                "ELSE 0 END".format(height_eligible)),
            ("current_month_stunting",
                "CASE "
                "WHEN NOT {} THEN NULL "
                "WHEN date_trunc('MONTH', gm.zscore_grading_hfa_last_recorded) != %(start_date)s "
                "   THEN 'unmeasured' "
                "WHEN gm.zscore_grading_hfa = 1 THEN 'severe' "
                "WHEN gm.zscore_grading_hfa = 2 THEN 'moderate' "
                "WHEN gm.zscore_grading_hfa = 3 THEN 'normal' "
                "ELSE 'unmeasured' END".format(height_eligible)),
            ("stunting_last_recorded",
                "CASE "
                "WHEN NOT {} THEN NULL "
                "WHEN gm.zscore_grading_hfa = 1 THEN 'severe' "
                "WHEN gm.zscore_grading_hfa = 2 THEN 'moderate' "
                "WHEN gm.zscore_grading_hfa = 3 THEN 'normal' "
                "ELSE 'unknown' END".format(height_eligible)),
            ("wasting_last_recorded",
                "CASE "
                "WHEN NOT {} THEN NULL "
                "WHEN gm.zscore_grading_wfh = 1 THEN 'severe' "
                "WHEN gm.zscore_grading_wfh = 2 THEN 'moderate' "
                "WHEN gm.zscore_grading_wfh = 3 THEN 'normal' "
                "ELSE 'unknown' END".format(height_eligible)),
            ("current_month_wasting",
                "CASE "
                "WHEN NOT {} THEN NULL "
                "WHEN date_trunc('MONTH', gm.zscore_grading_wfh_last_recorded) != %(start_date)s "
                "   THEN 'unmeasured' "
                "WHEN gm.zscore_grading_wfh = 1 THEN 'severe' "
                "WHEN gm.zscore_grading_wfh = 2 THEN 'moderate' "
                "WHEN gm.zscore_grading_wfh = 3 THEN 'normal' "
                "ELSE 'unmeasured' END".format(height_eligible)),
            ("zscore_grading_hfa", "gm.zscore_grading_hfa"),
            ("zscore_grading_hfa_recorded_in_month",
                "CASE WHEN (date_trunc('MONTH', gm.zscore_grading_hfa_last_recorded) = %(start_date)s) "
                "THEN 1 ELSE 0 END"),
            ("zscore_grading_wfh", "gm.zscore_grading_wfh"),
            ("zscore_grading_wfh_recorded_in_month",
                "CASE WHEN (date_trunc('MONTH', gm.zscore_grading_wfh_last_recorded) = %(start_date)s) "
                "THEN 1 ELSE 0 END"),
            ("muac_grading", "gm.muac_grading"),
            ("muac_grading_recorded_in_month",
                "CASE WHEN (date_trunc('MONTH', gm.muac_grading_last_recorded) = %(start_date)s) "
                "THEN 1 ELSE 0 END"),
            # CF Indicators
            ("cf_eligible", "CASE WHEN {} THEN 1 ELSE 0 END".format(cf_eligible)),
            ("cf_initiation_eligible", "CASE WHEN {} THEN 1 ELSE 0 END".format(cf_initiation_eligible)),
            ("cf_in_month",
                "CASE WHEN {} THEN COALESCE(cf.comp_feeding_latest, 0) ELSE 0 END".format(cf_eligible)),
            ("cf_diet_diversity",
                "CASE WHEN {} THEN COALESCE(cf.diet_diversity, 0) ELSE 0 END".format(cf_eligible)),
            ("cf_diet_quantity", "CASE WHEN {} THEN COALESCE(cf.diet_quantity, 0) ELSE 0 END".format(cf_eligible)),
            ("cf_handwashing", "CASE WHEN {} THEN COALESCE(cf.hand_wash, 0) ELSE 0 END".format(cf_eligible)),
            ("cf_demo", "CASE WHEN {} THEN COALESCE(cf.demo_comp_feeding, 0) ELSE 0 END".format(cf_eligible)),
            ("counsel_pediatric_ifa",
                "CASE WHEN {} THEN COALESCE(cf.counselled_pediatric_ifa, 0) ELSE 0 END".format(cf_eligible)),
            ("counsel_comp_feeding_vid",
                "CASE WHEN {} THEN COALESCE(cf.play_comp_feeding_vid, 0) ELSE 0 END".format(cf_eligible)),
            ("cf_initiation_in_month",
                "CASE WHEN {} THEN COALESCE(cf.comp_feeding_ever, 0) ELSE 0 END".format(cf_initiation_eligible)),
            # THR Indicators
            ("thr_eligible", "CASE WHEN {} THEN 1 ELSE 0 END".format(thr_eligible)),
            ("num_rations_distributed",
                "CASE WHEN {} THEN COALESCE(thr.days_ration_given_child, 0) ELSE NULL END".format(thr_eligible)),
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
            ("mother_phone_number", "child_health.mother_phone_number"),
            ("date_death", "child_health.date_death"),
            ("mother_case_id", "child_health.mother_case_id")
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (SELECT
            {calculations}
            FROM "{child_health_case_ucr}" child_health
            LEFT OUTER JOIN "{child_tasks_case_ucr}" child_tasks ON
              child_health.doc_id = child_tasks.child_health_case_id
              AND child_health.state_id = child_tasks.state_id
              AND lower(substring(child_tasks.state_id, '.{{3}}$'::text)) = %(state_id_last_3)s
              AND child_health.supervisor_id = child_tasks.supervisor_id
            LEFT OUTER JOIN "{person_cases_ucr}" person_cases ON child_health.mother_id = person_cases.doc_id
              AND child_health.state_id = person_cases.state_id
              AND lower(substring(person_cases.state_id, '.{{3}}$'::text)) = %(state_id_last_3)s
              AND child_health.supervisor_id = person_cases.supervisor_id
            LEFT OUTER JOIN "{agg_cf_table}" cf ON child_health.doc_id = cf.case_id AND cf.month = %(start_date)s
              AND child_health.state_id = cf.state_id
              AND child_health.supervisor_id = cf.supervisor_id
            LEFT OUTER JOIN "{agg_thr_table}" thr ON child_health.doc_id = thr.case_id
              AND thr.month = %(start_date)s
              AND child_health.state_id = thr.state_id
              AND child_health.supervisor_id = thr.supervisor_id
            LEFT OUTER JOIN "{agg_gm_table}" gm ON child_health.doc_id = gm.case_id
              AND gm.month = %(start_date)s
              AND child_health.state_id = gm.state_id
              AND child_health.supervisor_id = gm.supervisor_id
            LEFT OUTER JOIN "{agg_pnc_table}" pnc ON child_health.doc_id = pnc.case_id
              AND pnc.month = %(start_date)s
              AND child_health.state_id = pnc.state_id
              AND child_health.supervisor_id = pnc.supervisor_id
            LEFT OUTER JOIN "{agg_df_table}" df ON child_health.doc_id = df.case_id
              AND df.month = %(start_date)s
              AND child_health.state_id = df.state_id
              AND child_health.supervisor_id = df.supervisor_id
            WHERE child_health.doc_id IS NOT NULL
              AND child_health.state_id = %(state_id)s
              AND {open_in_month}
            ORDER BY child_health.supervisor_id, child_health.awc_id
        )
        """.format(
            tablename=self.temporary_tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            agg_cf_table=AGG_COMP_FEEDING_TABLE,
            agg_thr_table=AGG_CHILD_HEALTH_THR_TABLE,
            child_health_case_ucr=self.child_health_case_ucr_tablename,
            agg_gm_table=AGG_GROWTH_MONITORING_TABLE,
            agg_pnc_table=AGG_CHILD_HEALTH_PNC_TABLE,
            agg_df_table=AGG_DAILY_FEEDING_TABLE,
            child_tasks_case_ucr=self.child_tasks_case_ucr_tablename,
            person_cases_ucr=self.person_case_ucr_tablename,
            open_in_month=open_in_month
        ), {
            "start_date": self.month,
            "next_month": month_formatter(self.month + relativedelta(months=1)),
            "state_id": state_id,
            "state_id_last_3": state_id[-3:],
        }

    def pre_aggregation_queries(self):
        return [self._state_aggregation_query(state_id) for state_id in self.state_ids]

    def create_temporary_table(self):
        return """
        CREATE UNLOGGED TABLE \"{table}\" (LIKE child_health_monthly INCLUDING INDEXES);
        SELECT create_distributed_table('{table}', 'supervisor_id');
        """.format(table=self.temporary_tablename)

    def drop_temporary_table(self):
        return "DROP TABLE IF EXISTS \"{}\"".format(self.temporary_tablename)

    def aggregation_query(self):
        return "INSERT INTO \"{tablename}\" (SELECT * FROM \"{tmp_tablename}\")".format(
            tablename=self.tablename, tmp_tablename=self.temporary_tablename)

    def indexes(self):
        return [
            'CREATE INDEX IF NOT EXISTS chm_case_idx ON "{}" (case_id)'.format(self.tablename),
            'CREATE INDEX IF NOT EXISTS chm_awc_idx ON "{}" (awc_id)'.format(self.tablename),
            'CREATE INDEX IF NOT EXISTS chm_mother_dob ON "{}" (mother_case_id, dob)'.format(self.tablename),
        ]
