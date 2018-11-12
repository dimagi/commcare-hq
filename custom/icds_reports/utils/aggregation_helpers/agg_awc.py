from __future__ import absolute_import
from __future__ import unicode_literals

import six
from dateutil.relativedelta import relativedelta

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from six.moves import map

from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, transform_day_to_month, \
    month_formatter


class AggAwcHelper(BaseICDSAggregationHelper):
    base_tablename = 'agg_awc'
    ucr_data_source_id = 'static-awc_location'

    def __init__(self, month):
        self.month_start = transform_day_to_month(month)
        self.month_end = self.month_start + relativedelta(months=1, seconds=-1)
        self.prev_month = self.month_start - relativedelta(months=1)
        self.month_start_6m = self.month_start - relativedelta(months=6)
        self.month_end_11yr = self.month_end - relativedelta(years=11)
        self.month_start_15yr = self.month_start - relativedelta(years=15)
        self.month_end_15yr = self.month_end - relativedelta(years=15)
        self.month_start_18yr = self.month_start - relativedelta(years=18)

    def _tablename_func(self, agg_level):
        return "{}_{}_{}".format(self.base_tablename, self.month_start.strftime("%Y-%m-%d"), agg_level)

    @property
    def tablename(self):
        return self._tablename_func(5)

    def _ucr_tablename(self, ucr_id):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def aggregation_query(self):
        return """
        INSERT INTO "{tablename}"
        (
            state_id, district_id, block_id, supervisor_id, awc_id, month, num_awcs,
            is_launched, aggregation_level
        )
        (
            SELECT
            state_id,
            district_id,
            block_id,
            supervisor_id,
            doc_id AS awc_id,
            %(start_date)s,
            1,
            'no',
            5
            FROM "{ucr_table}"
        )
        """.format(
            tablename=self.tablename,
            ucr_table=self.ucr_tablename
        ), {
            'start_date': self.month_start
        }

    def indexes(self, aggregation_level):
        indexes = []

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
        if aggregation_level > 3:
            indexes.append('CREATE INDEX ON "{}" (awc_id)'.format(self.tablename))
            agg_locations.append('awc_id')

        indexes.append('CREATE INDEX ON "{}" ({})'.format(self.tablename, ', '.join(agg_locations)))
        return indexes

    def updates(self):
        yield """
        UPDATE "{tablename}" agg_awc SET
            awc_days_open = ut.awc_days_open,
            awc_num_open = ut.awc_num_open,
            awc_days_pse_conducted = ut.awc_days_pse_conducted
        FROM (
            SELECT
                awc_id,
                month,
                sum(awc_open_count) AS awc_days_open,
                CASE WHEN (sum(awc_open_count) > 0) THEN 1 ELSE 0 END AS awc_num_open,
                sum(pse_conducted) as awc_days_pse_conducted
            FROM "{daily_attendance}"
            WHERE month = %(start_date)s GROUP BY awc_id, month
        ) ut
        WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            daily_attendance='daily_attendance_{}'.format(month_formatter(self.month_start)),
        ), {
            'start_date': self.month_start
        }

        yield """
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
            FROM agg_child_health
            WHERE month = %(start_date)s AND aggregation_level = 5 GROUP BY awc_id, month
        ) ut
        WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id;
        """.format(
            tablename=self.tablename,
        ), {
            'start_date': self.month_start
        }

        yield """
        UPDATE "{tablename}" agg_awc SET
            cases_ccs_pregnant = ut.cases_ccs_pregnant,
            cases_ccs_lactating = ut.cases_ccs_lactating,
            cases_ccs_pregnant_all = ut.cases_ccs_pregnant_all,
            cases_ccs_lactating_all = ut.cases_ccs_lactating_all,
            cases_person_beneficiary_v2 = COALESCE(cases_person_beneficiary_v2, 0) + ut.cases_ccs_pregnant + ut.cases_ccs_lactating
        FROM (
            SELECT
                awc_id,
                month,
                sum(pregnant) AS cases_ccs_pregnant,
                sum(lactating) AS cases_ccs_lactating,
                sum(pregnant_all) AS cases_ccs_pregnant_all,
                sum(lactating_all) AS cases_ccs_lactating_all
            FROM agg_ccs_record
            WHERE month = %(start_date)s AND aggregation_level = 5 GROUP BY awc_id, month
        ) ut
        WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id;
        """.format(
            tablename=self.tablename,
        ), {
            'start_date': self.month_start
        }

        yield """
        UPDATE "{tablename}" agg_awc SET
           cases_household = ut.cases_household
        FROM (
            SELECT
                owner_id,
                sum(open_count) AS cases_household
            FROM "{household_cases}"
            GROUP BY owner_id
       ) ut
        WHERE ut.owner_id = agg_awc.awc_id
        """.format(
            tablename=self.tablename,
            household_cases=self._ucr_tablename('static-household_cases'),
        ), {}

        yield """
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
            FROM "{ucr_tablename}"
            WHERE (opened_on <= %(end_date)s AND (closed_on IS NULL OR closed_on >= %(start_date)s ))
            GROUP BY awc_id
        ) ut
        WHERE ut.awc_id = agg_awc.awc_id;
        """.format(
            tablename=self.tablename,
            ucr_tablename=self._ucr_tablename('static-person_cases_v2'),
        ), {
            'start_date': self.month_start,
            'end_date': self.month_end,
            'month_end_11yr': self.month_end_11yr,
            'month_start_15yr': self.month_start_15yr,
            'month_end_15yr': self.month_end_15yr,
            'month_start_18yr': self.month_start_18yr,
        }

        yield """
        UPDATE "{tablename}" agg_awc SET
            cases_person_has_aadhaar_v2 = ut.child_has_aadhar,
            num_children_immunized = ut.num_children_immunized
        FROM (
            SELECT
                awc_id,
                sum(has_aadhar_id) as child_has_aadhar,
                sum(immunization_in_month) AS num_children_immunized
            FROM "{child_health_monthly}"
            WHERE valid_in_month = 1
            GROUP BY awc_id
        ) ut
        WHERE ut.awc_id = agg_awc.awc_id;
        """.format(
            tablename=self.tablename,
            child_health_monthly="child_health_monthly_{}".format(self.month_start),
        ), {}

        yield """
        UPDATE "{tablename}" agg_awc SET
            num_anc_visits = ut.num_anc_visits,
            cases_person_has_aadhaar_v2 = COALESCE(cases_person_has_aadhaar_v2, 0) + ut.ccs_has_aadhar
        FROM (
            SELECT
                awc_id,
                sum(anc_in_month) AS num_anc_visits,
                sum(has_aadhar_id) AS ccs_has_aadhar
            FROM "{ccs_record_monthly}"
            WHERE pregnant = 1 OR lactating = 1
            GROUP BY awc_id
        ) ut
        WHERE ut.awc_id = agg_awc.awc_id;
        """.format(
            tablename=self.tablename,
            ccs_record_monthly="ccs_record_monthly_{}".format(self.month_start),
        ), {}

        yield """
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
            FROM "{usage_table}"
            WHERE month = %(start_date)s GROUP BY awc_id, month
        ) ut
        WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id;
        """.format(
            tablename=self.tablename,
            usage_table=self._ucr_tablename('static-usage_forms'),
        ), {
            'start_date': self.month_start
        }

        yield """
        UPDATE "{tablename}" agg_awc SET
            is_launched = 'yes',
            num_launched_awcs = 1
        FROM (
            SELECT DISTINCT(awc_id)
            FROM agg_awc
            WHERE month <= %(prev_month)s AND usage_num_hh_reg > 0 AND awc_id <> 'ALL'
        ) ut
        WHERE ut.awc_id = agg_awc.awc_id;
        """.format(
            tablename=self.tablename
        ), {
            'prev_month': self.prev_month
        }

        yield """
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
            FROM icds_dashboard_infrastructure_forms
            WHERE month = %(start_date)s
        ) ut
        WHERE ut.awc_id = agg_awc.awc_id;
            -- could possibly add multicol indexes to make order by faster?
        """.format(
            tablename=self.tablename,
        ), {
            'start_date': self.month_start
        }

        yield """
         UPDATE "{tablename}" agg_awc SET num_awc_infra_last_update =
          CASE WHEN infra_last_update_date IS NOT NULL AND
             %(month_start_6m)s < infra_last_update_date THEN 1 ELSE 0 END
        """.format(
            tablename=self.tablename
        ), {
            'month_start_6m': self.month_start_6m
        }

    def rollup_query(self, aggregation_level):

        launched_cols = [
            'num_launched_states',
            'num_launched_districts',
            'num_launched_blocks',
            'num_launched_supervisors',
            'num_launched_awcs',
        ]

        def _launched_col(col):
            col_index = launched_cols.index(col)
            col_for_level = launched_cols[aggregation_level]
            if col_index >= aggregation_level:
                return 'sum({})'.format(col)
            else:
                return 'CASE WHEN (sum({}) > 0) THEN 1 ELSE 0 END'.format(col_for_level)

        columns = [
            ('state_id', 'state_id'),
            ('district_id', lambda col: col if aggregation_level > 1 else "'All'"),
            ('block_id', lambda col: col if aggregation_level > 2 else "'All'"),
            ('supervisor_id', lambda col: col if aggregation_level > 3 else "'All'"),
            ('awc_id', lambda col: col if aggregation_level > 4 else "'All'"),
            ('month', 'month'),
            ('num_awcs',),
            ('awc_days_open',),
            ('awc_num_open',),
            ('wer_weighed',),
            ('wer_eligible',),
            ('cases_ccs_pregnant',),
            ('cases_ccs_lactating',),
            ('cases_child_health',),
            ('usage_num_pse',),
            ('usage_num_gmp',),
            ('usage_num_thr',),
            ('usage_num_home_visit',),
            ('usage_num_bp_tri1',),
            ('usage_num_bp_tri2',),
            ('usage_num_bp_tri3',),
            ('usage_num_pnc',),
            ('usage_num_ebf',),
            ('usage_num_cf',),
            ('usage_num_delivery',),
            ('usage_num_due_list_ccs',),
            ('usage_num_due_list_child_health',),
            ('usage_awc_num_active',),
            ('infra_last_update_date', 'NULL'),
            ('infra_type_of_building', 'NULL'),
            ('infra_clean_water',),
            ('infra_functional_toilet',),
            ('infra_baby_weighing_scale',),
            ('infra_adult_weighing_scale',),
            ('infra_cooking_utensils',),
            ('infra_medicine_kits',),
            ('infra_adequate_space_pse',),
            ('usage_num_hh_reg',),
            ('usage_num_add_person',),
            ('usage_num_add_pregnancy',),
            ('is_launched', "'yes'"),
            ('aggregation_level', str(aggregation_level)),
            ('num_launched_states', lambda col: _launched_col(col)),
            ('num_launched_districts', lambda col: _launched_col(col)),
            ('num_launched_blocks', lambda col: _launched_col(col)),
            ('num_launched_supervisors', lambda col: _launched_col(col)),
            ('num_launched_awcs', lambda col: _launched_col(col)),
            ('cases_household',),
            ('cases_person',),
            ('cases_person_all',),
            ('cases_ccs_pregnant_all',),
            ('cases_ccs_lactating_all',),
            ('cases_child_health_all',),
            ('cases_person_adolescent_girls_11_14',),
            ('cases_person_adolescent_girls_15_18',),
            ('cases_person_adolescent_girls_11_14_all',),
            ('cases_person_adolescent_girls_15_18_all',),
            ('infra_infant_weighing_scale',),
            ('cases_person_referred', 'NULL'),
            ('awc_days_pse_conducted', 'NULL'),
            ('num_awc_infra_last_update',),
            ('cases_person_has_aadhaar_v2',),
            ('cases_person_beneficiary_v2',),
            ('electricity_awc', 'COALESCE(sum(electricity_awc), 0)'),
            ('infantometer', 'COALESCE(sum(infantometer), 0)'),
            ('stadiometer', 'COALESCE(sum(stadiometer), 0)'),
            ('num_anc_visits', 'COALESCE(sum(num_anc_visits), 0)'),
            ('num_children_immunized', 'COALESCE(sum(num_children_immunized), 0)'),
        ]

        def _transform_column(column_tuple):
            column = column_tuple[0]

            if len(column_tuple) == 2:
                agg_col = column_tuple[1]
                if isinstance(agg_col, six.string_types):
                    return column_tuple
                elif callable(agg_col):
                    return (column, agg_col(column))

            return column, 'SUM({})'.format(column)

        columns = list(map(_transform_column, columns))

        group_by = ["state_id"]
        if aggregation_level > 1:
            group_by.append("district_id")
        if aggregation_level > 2:
            group_by.append("block_id")
        if aggregation_level > 3:
            group_by.append("supervisor_id")

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
            from_tablename=self._tablename_func(aggregation_level + 1),
            to_tablename=self._tablename_func(aggregation_level),
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            group_by=", ".join(group_by),
        )
