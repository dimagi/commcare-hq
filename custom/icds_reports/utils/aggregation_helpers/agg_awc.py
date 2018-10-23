from __future__ import absolute_import
from __future__ import unicode_literals

import six
from dateutil.relativedelta import relativedelta

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import AWC_LOCATION_TABLE_ID, USAGE_TABLE_ID, PERSON_TABLE_ID, HOUSEHOLD_TABLE_ID

from custom.icds_reports.utils.aggregation import BaseICDSAggregationHelper, date_to_string, month_formatter, \
    transform_day_to_month


class AggAwcAggregationHelper(BaseICDSAggregationHelper):
    base_tablename = 'agg_awc'
    infra_tablename = 'icds_dashboard_infrastructure_forms'
    ccs_record_tablename = 'agg_ccs_record'
    child_health_tablename = 'agg_child_health'
    awc_location_table_id = AWC_LOCATION_TABLE_ID
    usage_table = USAGE_TABLE_ID
    person_table = PERSON_TABLE_ID
    household_table = HOUSEHOLD_TABLE_ID
    daily_attendance_table = 'daily_attendance'
    ccs_record_monthly_table = 'ccs_record_monthly'
    child_health_monthly_table = 'child_health_monthly'

    def __init__(self, month):
        self.month = transform_day_to_month(month)

    @property
    def awc_location_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.awc_location_table_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def usage_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.usage_table)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def person_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.person_table)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def household_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.household_table)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def daily_attendance_tablename(self):
        return "{}_{}".format(self.daily_attendance_table, date_to_string(self.month))

    @property
    def ccs_record_monthly_tablename(self):
        return "{}_{}".format(self.ccs_record_monthly_table, date_to_string(self.month))

    @property
    def child_health_monthly_tablename(self):
        return "{}_{}".format(self.child_health_monthly_table, date_to_string(self.month))

    def _tablename_func(self, agg_level):
        return "{}_{}_{}".format(self.base_tablename, date_to_string(self.month), agg_level)

    @property
    def tablename(self):
        return self._tablename_func(5)

    def drop_table_query(self):
        return 'DELETE FROM "{}"'.format(self.tablename)

    def aggregate_query(self):
        # setup base locations and month

        columns = (
            ('state_id', 'state_id'),
            ('district_id', 'district_id'),
            ('block_id', 'block_id'),
            ('supervisor_id', 'supervisor_id'),
            ('awc_id', 'doc_id as awc_id'),
            ('month', self.month.strftime("'%Y-%m-%d'")),
            ('num_awcs', '1'),
            ('is_launched', "'no'"),
            ('aggregation_level', '5'),
        )

        return """
            INSERT INTO "{tablename}" (
              {columns}
            ) (
              SELECT {calculations} 
              FROM "{awc_location_tablename}"
            )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            awc_location_tablename=self.awc_location_tablename
        ), {}

    def aggregate_daily_attendance_query(self):
        return """
            UPDATE "{tablename}" agg_awc SET
              awc_days_open = ut.awc_days_open, 
              awc_num_open = ut.awc_num_open, 
              awc_days_pse_conducted = ut.awc_days_pse_conducted 
            FROM (
              SELECT
                awc_id, 
                month, 
                sum(awc_open_count) as awc_days_open, 
                CASE WHEN (sum(awc_open_count) > 0) THEN 1 ELSE 0 END AS awc_num_open, 
                sum(pse_conducted) as awc_days_pse_conducted 
              FROM "{daily_attendance_tablename}"
              WHERE month = %(start_date)s
              GROUP BY awc_id, month
            ) ut
            WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            daily_attendance_tablename=self.daily_attendance_tablename
        ), {
            "start_date": date_to_string(self.month)
        }

    def aggregate_monthly_child_health_query(self):
        return """
            UPDATE "{tablename}" agg_awc SET
              cases_child_health = ut.cases_child_health, 
              cases_child_health_all = ut.cases_child_health_all, 
              wer_weighed = ut.wer_weighed, 
              wer_eligible = ut.wer_eligible, 
              cases_person_beneficiary_v2 = ut.cases_child_health 
            FROM (
              SELECT
                awc_id, 
                month, 
                sum(valid_in_month) AS cases_child_health, 
                sum(valid_all_registered_in_month) AS cases_child_health_all, 
                sum(nutrition_status_weighed) AS wer_weighed, 
                sum(wer_eligible) AS wer_eligible 
              FROM "{child_health_tablename}"
              WHERE month = %(start_date)s and aggregation_level = 5
              GROUP BY awc_id, month
            ) ut
            WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            child_health_tablename=self.child_health_tablename
        ), {
            "start_date": date_to_string(self.month)
        }
    
    def aggregate_ccs_record_query(self):
        return """
            UPDATE "{tablename}" agg_awc SET  
              cases_ccs_pregnant = ut.cases_ccs_pregnant, 
              cases_ccs_lactating = ut.cases_ccs_lactating, 
              cases_ccs_pregnant_all = ut.cases_ccs_pregnant_all, 
              cases_ccs_lactating_all = ut.cases_ccs_lactating_all, 
              cases_person_beneficiary_v2 = COALESCE(cases_person_beneficiary_v2, 0) + ut.cases_ccs_pregnant + ut.cases_ccs_lactating 
            FROM (SELECT  
              awc_id,  
              month,  
              sum(pregnant) AS cases_ccs_pregnant, 
              sum(lactating) AS cases_ccs_lactating, 
              sum(pregnant_all) AS cases_ccs_pregnant_all, 
              sum(lactating_all) AS cases_ccs_lactating_all 
              FROM "{ccs_record_tablename}" 
              WHERE month = %(start_date)s AND aggregation_level = 5 GROUP BY awc_id, month) ut 
            WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id;
        """.format(
            tablename=self.tablename,
            ccs_record_tablename=self.ccs_record_tablename
        ), {
            "start_date": date_to_string(self.month)
        }

    def aggregate_household_query(self):
        return """
            UPDATE "{tablename}" agg_awc SET 
              cases_household = ut.cases_household 
            FROM (
              SELECT 
                owner_id, 
                sum(open_count) as cases_household 
              FROM "{household_tablename}" 
              GROUP BY owner_id
            ) ut
            WHERE ut.owner_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            household_tablename=self.household_tablename
        ), {}

    def aggregate_person_query(self):
        end_month = self.month + relativedelta(months=1) - relativedelta(days=1)
        month_end_11yr = end_month - relativedelta(years=11)
        month_start_15yr = self.month - relativedelta(years=15)
        month_end_15yr = end_month - relativedelta(years=15)
        month_start_18yr = self.month - relativedelta(years=18)
        return """
            UPDATE "{tablename}" agg_awc SET 
              cases_person = ut.cases_person, 
              cases_person_all = ut.cases_person_all, 
              cases_person_adolescent_girls_11_14 = ut.cases_person_adolescent_girls_11_14, 
              cases_person_adolescent_girls_11_14_all = ut.cases_person_adolescent_girls_11_14_all, 
              cases_person_adolescent_girls_15_18 = ut.cases_person_adolescent_girls_15_18, 
              cases_person_adolescent_girls_15_18_all = ut.cases_person_adolescent_girls_15_18_all, 
              cases_person_referred = ut.cases_person_referred 
            FROM (
              SELECT
                awc_id, 
                sum(seeking_services) AS cases_person, 
                sum(count) AS cases_person_all, 
                sum(CASE WHEN %(month_end_11yr)s > dob AND %(month_start_15yr)s <= dob AND sex = 'F' THEN seeking_services ELSE 0 END) as cases_person_adolescent_girls_11_14, 
                sum(CASE WHEN %(month_end_11yr)s > dob AND %(month_start_15yr)s <= dob AND sex = 'F' THEN 1 ELSE 0 END) as cases_person_adolescent_girls_11_14_all, 
                sum(CASE WHEN %(month_end_15yr)s > dob AND %(month_start_18yr)s <= dob AND sex = 'F' THEN seeking_services ELSE 0 END) as cases_person_adolescent_girls_15_18, 
                sum(CASE WHEN %(month_end_15yr)s > dob AND %(month_start_18yr)s <= dob AND sex = 'F' THEN 1 ELSE 0 END) as cases_person_adolescent_girls_15_18_all, 
                sum(CASE WHEN last_referral_date BETWEEN %(start_date)s AND %(end_date)s THEN 1 ELSE 0 END) as cases_person_referred 
              FROM "{person_tablename}" 
              WHERE (opened_on <= %(end_date)s AND (closed_on IS NULL OR closed_on >= %(start_date)s)) 
              GROUP BY awc_id
            ) ut 
            WHERE ut.awc_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            person_tablename=self.person_tablename
        ), {
            "start_date": date_to_string(self.month),
            "end_date": date_to_string(end_month),
            "month_end_11yr": date_to_string(month_end_11yr),
            "month_start_15yr": date_to_string(month_start_15yr),
            "month_end_15yr": date_to_string(month_end_15yr),
            "month_start_18yr": date_to_string(month_start_18yr),
        }

    def children_immunized_query(self):
        return """
            UPDATE "{tablename}" agg_awc SET 
              cases_person_has_aadhaar_v2 = ut.child_has_aadhar, 
              num_children_immunized = ut.num_children_immunized 
            FROM (
              SELECT 
                awc_id, 
                sum(has_aadhar_id) as child_has_aadhar, 
                sum(immunization_in_month) AS num_children_immunized 
              FROM "{child_health_monthly_tablename}" 
              WHERE valid_in_month = 1 
              GROUP BY awc_id 
            ) ut 
            WHERE ut.awc_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            child_health_monthly_tablename=self.child_health_monthly_tablename
        ), {}

    def number_anc_visits_query(self):
        return """
            UPDATE "{tablename}" agg_awc SET 
              num_anc_visits = ut.num_anc_visits, 
              cases_person_has_aadhaar_v2 = COALESCE(cases_person_has_aadhaar_v2, 0) + ut.ccs_has_aadhar 
            FROM (
              SELECT 
                awc_id, 
                sum(anc_in_month) AS num_anc_visits, 
                sum(has_aadhar_id) AS ccs_has_aadhar 
              FROM "{ccs_record_monthly_tablename}" 
              WHERE pregnant = 1 OR lactating = 1 
              GROUP BY awc_id
            ) ut 
            WHERE ut.awc_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            ccs_record_monthly_tablename=self.ccs_record_monthly_tablename
        ), {}

    def usage_table_query(self):
        return """
            UPDATE "{tablename}" agg_awc SET 
              usage_num_pse = ut.usage_num_pse, 
              usage_num_gmp = ut.usage_num_gmp, 
              usage_num_thr = ut.usage_num_thr, 
              usage_num_hh_reg = ut.usage_num_hh_reg, 
              is_launched = ut.is_launched, 
              num_launched_states = ut.num_launched_awcs, 
              num_launched_districts = ut.num_launched_awcs, 
              num_launched_blocks = ut.num_launched_awcs, 
              num_launched_supervisors = ut.num_launched_awcs, 
              num_launched_awcs = ut.num_launched_awcs, 
              usage_num_add_person = ut.usage_num_add_person, 
              usage_num_add_pregnancy = ut.usage_num_add_pregnancy, 
              usage_num_home_visit = ut.usage_num_home_visit, 
              usage_num_bp_tri1 = ut.usage_num_bp_tri1, 
              usage_num_bp_tri2 = ut.usage_num_bp_tri2, 
              usage_num_bp_tri3 = ut.usage_num_bp_tri3, 
              usage_num_pnc = ut.usage_num_pnc, 
              usage_num_ebf = ut.usage_num_ebf, 
              usage_num_cf = ut.usage_num_cf, 
              usage_num_delivery = ut.usage_num_delivery, 
              usage_awc_num_active = ut.usage_awc_num_active, 
              usage_num_due_list_ccs = ut.usage_num_due_list_ccs, 
              usage_num_due_list_child_health = ut.usage_num_due_list_child_health 
            FROM (
              SELECT 
                awc_id, 
                month, 
                sum(pse) AS usage_num_pse, 
                sum(gmp) AS usage_num_gmp, 
                sum(thr) AS usage_num_thr, 
                sum(add_household) AS usage_num_hh_reg, 
                CASE WHEN sum(add_household) > 0 THEN 'yes' ELSE 'no' END as is_launched, 
                CASE WHEN sum(add_household) > 0 THEN 1 ELSE 0 END as num_launched_awcs, 
                sum(add_person) AS usage_num_add_person, 
                sum(add_pregnancy) AS usage_num_add_pregnancy, 
                sum(home_visit) AS usage_num_home_visit, 
                sum(bp_tri1) AS usage_num_bp_tri1, 
                sum(bp_tri2) AS usage_num_bp_tri2, 
                sum(bp_tri3) AS usage_num_bp_tri3, 
                sum(pnc) AS usage_num_pnc, 
                sum(ebf) AS usage_num_ebf, 
                sum(cf) AS usage_num_cf, 
                sum(delivery) AS usage_num_delivery, 
                CASE WHEN (sum(due_list_ccs) + sum(due_list_child) + sum(pse) + sum(gmp) + sum(thr) + sum(home_visit) + sum(add_pregnancy) + sum(add_household)) >= 15 THEN 1 ELSE 0 END AS usage_awc_num_active, 
                sum(due_list_ccs) AS usage_num_due_list_ccs, 
                sum(due_list_child) AS usage_num_due_list_child_health 
              FROM "{usage_tablename}" 
              WHERE month = %(start_date)s 
              GROUP BY awc_id, month
            ) ut 
            WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            usage_tablename=self.usage_tablename
        ), {
            "start_date": date_to_string(self.month)
        }

    def number_launched_awcs_query(self):
        # Update num launched AWCs based on previous month as well
        return """
            UPDATE "{tablename}" agg_awc SET 
              is_launched = 'yes', 
              num_launched_awcs = 1 
            FROM (
              SELECT 
                DISTINCT (awc_id) 
              FROM "agg_awc" 
              WHERE month = %(previous_month)s AND num_launched_awcs > 0 AND aggregation_level = 5
              GROUP BY awc_id
            ) ut 
            WHERE ut.awc_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
        ), {
            "previous_month": month_formatter(self.month - relativedelta(months=1))
        }

    def latest_infrastructure_query(self):
        return """
            UPDATE "{tablename}" agg_awc SET 
              infra_last_update_date = ut.infra_last_update_date, 
              infra_type_of_building = ut.infra_type_of_building, 
              infra_clean_water = ut.infra_clean_water, 
              infra_functional_toilet = ut.infra_functional_toilet, 
              infra_baby_weighing_scale = ut.infra_baby_weighing_scale, 
              infra_adult_weighing_scale = ut.infra_adult_weighing_scale, 
              infra_infant_weighing_scale = ut.infra_infant_weighing_scale, 
              infra_cooking_utensils = ut.infra_cooking_utensils, 
              infra_medicine_kits = ut.infra_medicine_kits, 
              infra_adequate_space_pse = ut.infra_adequate_space_pse, 
              electricity_awc = ut.electricity_awc, 
              infantometer = ut.infantometer, 
              stadiometer = ut.stadiometer 
            FROM (
              SELECT 
                awc_id,
                month,
                latest_time_end_processed::date AS infra_last_update_date, 
                CASE
                  WHEN awc_building = 1 THEN 'pucca' 
                  WHEN awc_building = 2 THEN 'semi_pucca' 
                  WHEN awc_building = 3 THEN 'kuccha' 
                  WHEN awc_building = 4 THEN 'partial_covered_space' 
                ELSE NULL END AS infra_type_of_building, 
                CASE WHEN source_drinking_water IN (1, 2, 3) THEN 1 ELSE 0 END AS infra_clean_water, 
                toilet_functional AS infra_functional_toilet, 
                baby_scale_usable AS infra_baby_weighing_scale, 
                GREATEST(adult_scale_available, adult_scale_usable, 0) AS infra_adult_weighing_scale, 
                GREATEST(baby_scale_available, flat_scale_available, baby_scale_usable, 0) AS infra_infant_weighing_scale, 
                cooking_utensils_usable AS infra_cooking_utensils, 
                medicine_kits_usable AS infra_medicine_kits, 
                CASE WHEN adequate_space_pse = 1 THEN 1 ELSE 0 END AS infra_adequate_space_pse, 
                electricity_awc AS electricity_awc, 
                infantometer_usable AS infantometer, 
                stadiometer_usable AS stadiometer 
              FROM "{infra_tablename}" 
              WHERE month = %(start_date)s 
              GROUP BY awc_id
            ) ut
            WHERE ut.awc_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            infra_tablename=self.infra_tablename
        ), {
            "start_date": date_to_string(self.month)
        }

    def location_is_test_query(self):
        return """
            UPDATE "{tablename}" agg_awc SET 
              state_is_test = ut.state_is_test, 
              district_is_test = ut.district_is_test, 
              block_is_test = ut.block_is_test, 
              supervisor_is_test = ut.supervisor_is_test, 
              awc_is_test = ut.awc_is_test
            FROM (
              SELECT
                doc_id as awc_id,
                state_is_test, 
                district_is_test, 
                block_is_test, 
                supervisor_is_test, 
                awc_is_test 
              FROM "{awc_location_tablename}" 
              GROUP BY awc_id
            ) ut
            WHERE ut.awc_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            awc_location_tablename=self.awc_location_tablename
        ), {
            "start_date": date_to_string(self.month)
        }

    def infra_last_update_query(self):
        month_start_6m = self.month - relativedelta(months=6)
        infra_sql = 'CASE WHEN {inf_column} IS NOT NULL AND {month_start_6m} < {inf_column} THEN 1 ELSE 0 END'.format(
            inf_column="infra_last_update_date",
            month_start_6m=month_start_6m.strftime("'%Y-%m-%d'")
        )
        return """
            UPDATE "{tablename}" agg_awc SET
              num_awc_infra_last_update = {infra_sql}
        """.format(
            tablename=self.tablename,
            infra_sql=infra_sql
        ), {}

    def rollup_query(self, aggregation_level):

        def num_launched_column(agg_level, col_level):
            loc_levels = ['districts', 'blocks', 'supervisors', 'awcs']
            if col_level > agg_level:
                num_launched_col = 'num_launched_{loc_level}'.format(loc_level=loc_levels[col_level - 2])
                return 'sum({column})'.format(column=num_launched_col)
            else:
                num_launched_col = 'num_launched_{loc_level}'.format(loc_level=loc_levels[agg_level - 1])
                return 'CASE WHEN (sum({column}) > 0) THEN 1 ELSE 0 END'.format(column=num_launched_col)

        columns = (
            ('state_id', 'state_id'),
            ('district_id', lambda col: col if aggregation_level > 1 else "'All'"),
            ('block_id', lambda col: col if aggregation_level > 2 else "'All'"),
            ('supervisor_id', lambda col: col if aggregation_level > 3 else "'All'"),
            ('awc_id', lambda col: col if aggregation_level > 4 else "'All'"),
            ('month', 'month'),
            ('num_awcs', 'sum(num_awcs)'),
            ('awc_days_open', 'sum(awc_days_open)'),
            ('awc_num_open', 'sum(awc_num_open)'),
            ('wer_weighed', 'sum(wer_weighed)'),
            ('wer_eligible', 'sum(wer_eligible)'),
            ('cases_ccs_pregnant', 'sum(cases_ccs_pregnant)'),
            ('cases_ccs_lactating', 'sum(cases_ccs_lactating)'),
            ('cases_child_health', 'sum(cases_child_health)'),
            ('usage_num_pse', 'sum(usage_num_pse)'),
            ('usage_num_gmp', 'sum(usage_num_gmp)'),
            ('usage_num_thr', 'sum(usage_num_thr)'),
            ('usage_num_home_visit', 'sum(usage_num_home_visit)'),
            ('usage_num_bp_tri1', 'sum(usage_num_bp_tri1)'),
            ('usage_num_bp_tri2', 'sum(usage_num_bp_tri2)'),
            ('usage_num_bp_tri3', 'sum(usage_num_bp_tri3)'),
            ('usage_num_pnc', 'sum(usage_num_pnc)'),
            ('usage_num_ebf', 'sum(usage_num_ebf)'),
            ('usage_num_cf', 'sum(usage_num_cf)'),
            ('usage_num_delivery', 'sum(usage_num_delivery)'),
            ('usage_num_due_list_ccs', 'sum(usage_num_due_list_ccs)'),
            ('usage_num_due_list_child_health', 'sum(usage_num_due_list_child_health)'),
            ('usage_awc_num_active', 'sum(usage_awc_num_active)'),
            ('infra_last_update_date', "NULL"),
            ('infra_type_of_building', "NULL"),
            ('infra_clean_water', 'sum(infra_clean_water)'),
            ('infra_functional_toilet', 'sum(infra_functional_toilet)'),
            ('infra_baby_weighing_scale', 'sum(infra_baby_weighing_scale)'),
            ('infra_adult_weighing_scale', 'sum(infra_adult_weighing_scale)'),
            ('infra_cooking_utensils', 'sum(infra_cooking_utensils)'),
            ('infra_medicine_kits', 'sum(infra_medicine_kits)'),
            ('infra_adequate_space_pse', 'sum(infra_adequate_space_pse)'),
            ('usage_num_hh_reg', 'sum(usage_num_hh_reg)'),
            ('usage_num_add_person', 'sum(usage_num_add_person)'),
            ('usage_num_add_pregnancy', 'sum(usage_num_add_pregnancy)'),
            ('is_launched', "'yes'"),
            ('aggregation_level', "'{}'".format(aggregation_level)),
            ('num_launched_states', num_launched_column(aggregation_level, 1)),
            ('num_launched_districts', num_launched_column(aggregation_level, 2)),
            ('num_launched_blocks', num_launched_column(aggregation_level, 3)),
            ('num_launched_supervisors', num_launched_column(aggregation_level, 4)),
            ('num_launched_awcs', num_launched_column(aggregation_level, 5)),
            ('cases_household', 'sum(cases_household)'),
            ('cases_person', 'sum(cases_person)'),
            ('cases_person_all', 'sum(cases_person_all)'),
            ('cases_ccs_pregnant_all', 'sum(cases_ccs_pregnant_all)'),
            ('cases_ccs_lactating_all', 'sum(cases_ccs_lactating_all)'),
            ('cases_child_health_all', 'sum(cases_child_health_all)'),
            ('cases_person_adolescent_girls_11_14', 'sum(cases_person_adolescent_girls_11_14)'),
            ('cases_person_adolescent_girls_15_18', 'sum(cases_person_adolescent_girls_15_18)'),
            ('cases_person_adolescent_girls_11_14_all', 'sum(cases_person_adolescent_girls_11_14_all)'),
            ('cases_person_adolescent_girls_15_18_all', 'sum(cases_person_adolescent_girls_15_18_all)'),
            ('infra_infant_weighing_scale', 'sum(infra_infant_weighing_scale)'),
            ('cases_person_referred', "NULL"),
            ('awc_days_pse_conducted', "NULL"),
            ('num_awc_infra_last_update', 'sum(num_awc_infra_last_update)'),
            ('cases_person_has_aadhaar_v2', 'sum(cases_person_has_aadhaar_v2)'),
            ('cases_person_beneficiary_v2', 'sum(cases_person_beneficiary_v2)'),
            ('electricity_awc', 'COALESCE(sum(electricity_awc), 0)'),
            ('infantometer', 'COALESCE(sum(infantometer), 0)'),
            ('stadiometer', 'COALESCE(sum(stadiometer), 0)'),
            ('num_anc_visits', 'COALESCE(sum(num_anc_visits), 0)'),
            ('num_children_immunized', 'COALESCE(sum(num_children_immunized), 0)'),
            ('state_is_test', lambda col: col if aggregation_level > 1 else "0"),
            ('district_is_test', lambda col: col if aggregation_level > 2 else "0"),
            ('block_is_test', lambda col: col if aggregation_level > 3 else "0"),
            ('supervisor_is_test', lambda col: col if aggregation_level > 4 else "0"),
            ('awc_is_test', lambda col: col if aggregation_level > 5 else "0")
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

        group_by = ["state_id", "state_is_test"]
        if aggregation_level > 1:
            group_by.extend(["district_id", "district_is_test"])
        if aggregation_level > 2:
            group_by.extend(["block_id", "block_is_test"])
        if aggregation_level > 3:
            group_by.extend(["supervisor_id", "supervisor_is_test"])

        group_by.append("month")

        return """
                INSERT INTO "{to_tablename}" (
                    {columns}
                ) (
                    SELECT {calculations} 
                    FROM "{from_tablename}" 
                    GROUP BY {group_by}
                )
                """.format(
            to_tablename=self._tablename_func(aggregation_level),
            from_tablename=self._tablename_func(aggregation_level + 1),
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            group_by=", ".join(group_by),
        )

    def indexes(self, aggregation_level):
        all_loc_columns = ["state_id", "district_id", "block_id", "supervisor_id", "awc_id"]
        indexes = [
            'CREATE INDEX "{tablename}_indx1" ON "{tablename}" ({indx_columns})'.format(
                tablename=self._tablename_func(aggregation_level),
                indx_columns=", ".join(all_loc_columns[0:aggregation_level])
            ),
        ]
        if aggregation_level > 1:
            indexes.append('CREATE INDEX "{tablename}_indx2" ON "{tablename}" (district_id)'.format(
                tablename=self._tablename_func(aggregation_level))
            )
        if aggregation_level > 2:
            indexes.append('CREATE INDEX "{tablename}_indx3" ON "{tablename}" (block_id)'.format(
                tablename=self._tablename_func(aggregation_level))
            )
        if aggregation_level > 3:
            indexes.append('CREATE INDEX "{tablename}_indx4" ON "{tablename}"(supervisor_id)'.format(
                tablename=self._tablename_func(aggregation_level))
            )
        if aggregation_level > 4:
            indexes.append('CREATE INDEX "{tablename}_indx5" ON "{tablename}" (awc_id)'.format(
                tablename=self._tablename_func(aggregation_level))
            )

        return indexes