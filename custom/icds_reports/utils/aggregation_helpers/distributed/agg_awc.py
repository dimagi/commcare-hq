import logging

from dateutil.relativedelta import relativedelta

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from corehq.toggles import ICDS_LOCATION_REASSIGNMENT_AGG

from custom.icds_reports.utils.aggregation_helpers import get_child_health_temp_tablename, transform_day_to_month, get_agg_child_temp_tablename, get_prev_agg_tablename, is_current_month
from custom.icds_reports.const import AGG_CCS_RECORD_CF_TABLE, AGG_THR_V2_TABLE, AGG_ADOLESCENT_GIRLS_REGISTRATION_TABLE
from custom.icds_reports.const import (
    AGG_CCS_RECORD_CF_TABLE,
    AGG_THR_V2_TABLE,
    AGG_ADOLESCENT_GIRLS_REGISTRATION_TABLE,
    AGG_MIGRATION_TABLE,
    AGG_AVAILING_SERVICES_TABLE
)
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper

logger = logging.getLogger(__name__)


class AggAwcDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'agg-awc'
    base_tablename = 'agg_awc'

    def __init__(self, month):
        self.month_start = transform_day_to_month(month)
        self.month_end = self.month_start + relativedelta(months=1, seconds=-1)
        self.prev_month = self.month_start - relativedelta(months=1)
        self.month_start_6m = self.month_start - relativedelta(months=6)
        self.month_end_11yr = self.month_end - relativedelta(years=11)
        self.month_start_15yr = self.month_start - relativedelta(years=15)
        self.month_start_14yr = self.month_start - relativedelta(years=14)
        self.month_end_15yr = self.month_end - relativedelta(years=15)
        self.month_start_18yr = self.month_start - relativedelta(years=18)

    @property
    def child_temp_tablename(self):
        return get_child_health_temp_tablename(self.month_start)

    @property
    def agg_child_temp_tablename(self):
        return get_agg_child_temp_tablename()

    def get_table(self, table_id):
        if not is_current_month(self.month_start) and ICDS_LOCATION_REASSIGNMENT_AGG.enabled(self.domain):
            return get_prev_agg_tablename(table_id)
        return get_table_name(self.domain, table_id)

    def aggregate(self, cursor):
        agg_query, agg_params = self.aggregation_query()
        update_queries = self.updates()
        rollup_queries = [self.rollup_query(i) for i in range(4, 0, -1)]
        index_queries = [self.indexes(i) for i in range(5, 0, -1)]
        index_queries = [query for index_list in index_queries for query in index_list]

        cursor.execute(self.create_temporary_table())
        cursor.execute(agg_query, agg_params)
        i = 0
        for query, params in update_queries:
            logger.info(f"running update {i}")
            cursor.execute(query, params)
            i += 1
        i = 0
        for query in rollup_queries:
            logger.info(f"running rollup {i}")
            cursor.execute(query)
            i += 1
        i = 0
        for query in index_queries:
            logger.info(f"creating index {i}")
            cursor.execute(query)
            i += 1

    def _tablename_func(self, agg_level):
        return "{}_{}_{}".format(self.base_tablename, self.month_start.strftime("%Y-%m-%d"), agg_level)

    @property
    def tablename(self):
        return self._tablename_func(5)

    @property
    def temporary_tablename(self):
        return 'tmp_{}'.format(self.tablename)

    def aggregation_query(self):
        return """
        INSERT INTO "{tablename}"
        (
            state_id, district_id, block_id, supervisor_id, awc_id, month, num_awcs,
            is_launched, aggregation_level,  num_awcs_conducted_vhnd, num_awcs_conducted_cbe,
            cbe_conducted, vhnd_conducted, thr_distribution_image_count, num_launched_awcs,
            num_launched_supervisors, num_launched_blocks, num_launched_districts, num_launched_states
        )
        (
            SELECT
            awc_location.state_id,
            awc_location.district_id,
            awc_location.block_id,
            awc_location.supervisor_id,
            awc_location.doc_id AS awc_id,
            %(start_date)s,
            1,
            'no',
            5,
            CASE WHEN vhnd_conducted is not null and vhnd_conducted>0 THEN 1 ELSE 0 END,
            CASE WHEN cbe_conducted is not null and cbe_conducted>1 THEN 1 ELSE 0 END,
            cbe_conducted,
            vhnd_conducted,
            thr_v2.thr_distribution_image_count,
            0,
            0,
            0,
            0,
            0
            FROM awc_location_local awc_location
            LEFT JOIN (
                        select awc_id,
                               count(*) as cbe_conducted from
                            "{cbe_table}"
                                WHERE date_trunc('MONTH', date_cbe_organise) = %(start_date)s
                                GROUP BY awc_id
                        ) cbe_table on  awc_location.doc_id = cbe_table.awc_id
            LEFT JOIN (
                        SELECT awc_id,
                               count(*) as vhnd_conducted from
                                "{vhnd_table}"
                                WHERE date_trunc('MONTH', vhsnd_date_past_month) = %(start_date)s
                                GROUP BY awc_id
                        ) vhnd_table on awc_location.doc_id = vhnd_table.awc_id
            LEFT JOIN "{thr_v2_table}" thr_v2 on (awc_location.doc_id = thr_v2.awc_id AND
                                                thr_v2.month = %(start_date)s
                                                )
            WHERE awc_location.aggregation_level = 5
        )
        """.format(
            tablename=self.temporary_tablename,
            cbe_table=get_table_name(self.domain, 'static-cbe_form'),
            vhnd_table=get_table_name(self.domain, 'static-vhnd_form'),

            thr_v2_table=AGG_THR_V2_TABLE
        ), {
            'start_date': self.month_start
        }

    def indexes(self, aggregation_level):
        indexes = []

        tablename = self._tablename_func(aggregation_level)
        agg_locations = ['state_id']
        if aggregation_level > 1:
            indexes.append('CREATE INDEX ON "{}" (district_id)'.format(tablename))
            agg_locations.append('district_id')
        if aggregation_level > 2:
            indexes.append('CREATE INDEX ON "{}" (block_id)'.format(tablename))
            agg_locations.append('block_id')
        if aggregation_level > 3:
            indexes.append('CREATE INDEX ON "{}" (supervisor_id)'.format(tablename))
            agg_locations.append('supervisor_id')
        if aggregation_level > 3:
            indexes.append('CREATE INDEX ON "{}" (awc_id)'.format(tablename))
            agg_locations.append('awc_id')

        indexes.append('CREATE INDEX ON "{}" ({})'.format(tablename, ', '.join(agg_locations)))
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
                supervisor_id,
                month,
                sum(awc_open_count) AS awc_days_open,
                CASE WHEN (sum(awc_open_count) > 0) THEN 1 ELSE 0 END AS awc_num_open,
                sum(pse_conducted) as awc_days_pse_conducted
            FROM "{daily_attendance}"
            WHERE month = %(start_date)s GROUP BY awc_id, month, supervisor_id
        ) ut
        WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id and agg_awc.supervisor_id=ut.supervisor_id;
        """.format(
            tablename=self.temporary_tablename,
            daily_attendance='daily_attendance',
        ), {
            'start_date': self.month_start
        }

        # MAKE SURE YOU DID NOT RUIN PERFORMANCE
        yield """
        UPDATE "{tablename}" agg_awc SET
           cases_household = ut.cases_household,
           is_launched = CASE WHEN ut.all_cases_household>0 THEN 'yes' ELSE 'no' END,
           num_launched_states = CASE WHEN ut.all_cases_household>0 THEN 1 ELSE 0 END,
           num_launched_districts = CASE WHEN ut.all_cases_household>0 THEN 1 ELSE 0 END,
           num_launched_blocks = CASE WHEN ut.all_cases_household>0 THEN 1 ELSE 0 END,
           num_launched_supervisors = CASE WHEN ut.all_cases_household>0 THEN 1 ELSE 0 END,
           num_launched_awcs = CASE WHEN ut.all_cases_household>0 THEN 1 ELSE 0 END
        FROM ( SELECT
            awc_id,
            supervisor_id,
            sum(open_count) AS cases_household,
            count(*) AS all_cases_household
            FROM "{household_cases}"
            WHERE opened_on<= %(end_date)s
            GROUP BY awc_id, supervisor_id ) ut
        WHERE ut.awc_id = agg_awc.awc_id and ut.supervisor_id=agg_awc.supervisor_id;
        """.format(
            tablename=self.temporary_tablename,
            household_cases=self.get_table('static-household_cases')
        ), {'end_date': self.month_end}

        yield """
        UPDATE "{tablename}" agg_awc SET
           cases_person = ut.cases_person,
           cases_person_all = ut.cases_person_all,
           cases_person_adolescent_girls_11_14 = ut.cases_person_adolescent_girls_11_14,
           cases_person_adolescent_girls_11_14_all = ut.cases_person_adolescent_girls_11_14_all,
           cases_person_adolescent_girls_15_18 = ut.cases_person_adolescent_girls_15_18,
           cases_person_adolescent_girls_15_18_all = ut.cases_person_adolescent_girls_15_18_all,
           cases_person_referred = ut.cases_person_referred,
           cases_person_adolescent_girls_11_14_all_v2 = ut.cases_person_adolescent_girls_11_14_all_v2,
           cases_person_adolescent_girls_11_14_out_of_school=0
        FROM (
        SELECT
            ucr.awc_id,
            ucr.supervisor_id,
            sum({seeking_services}) AS cases_person,
            count(*) AS cases_person_all,
            sum(CASE WHEN
                %(month_end_11yr)s > dob AND %(month_start_15yr)s <= dob AND sex = 'F'
                THEN ({seeking_services}) ELSE 0 END
            ) as cases_person_adolescent_girls_11_14,
            sum(
                CASE WHEN %(month_end_11yr)s > dob AND %(month_start_15yr)s <= dob AND sex = 'F'
                THEN 1 ELSE 0 END
            ) as cases_person_adolescent_girls_11_14_all,
            sum(
                CASE WHEN %(month_end_11yr)s > dob AND %(month_start_14yr)s <= dob AND sex = 'F'
                    AND (agg_migration.is_migrated IS DISTINCT FROM 1 OR agg_migration.migration_date::date >= %(start_date)s)
                THEN 1 ELSE 0 END
            ) as cases_person_adolescent_girls_11_14_all_v2,
            sum(
                CASE WHEN %(month_end_15yr)s > dob AND %(month_start_18yr)s <= dob AND sex = 'F'
                THEN ({seeking_services}) ELSE 0 END
            ) as cases_person_adolescent_girls_15_18,
            sum(
                CASE WHEN %(month_end_15yr)s > dob AND %(month_start_18yr)s <= dob AND sex = 'F'
                    AND (agg_migration.is_migrated IS DISTINCT FROM 1 OR agg_migration.migration_date::date >= %(start_date)s)
                THEN 1 ELSE 0 END
            ) as cases_person_adolescent_girls_15_18_all,
            sum(
                CASE WHEN last_referral_date BETWEEN %(start_date)s AND %(end_date)s
                THEN 1 ELSE 0 END
            ) as cases_person_referred
        FROM "{ucr_tablename}" ucr LEFT JOIN
             "{migration_table}" agg_migration ON (
                ucr.doc_id = agg_migration.person_case_id AND
                agg_migration.month = %(start_date)s AND
                ucr.supervisor_id = agg_migration.supervisor_id
             ) LEFT JOIN
             "{availing_services_table}" agg_availing ON (
                ucr.doc_id = agg_availing.person_case_id AND
                agg_availing.month = %(start_date)s AND
                ucr.supervisor_id = agg_availing.supervisor_id
             )
        WHERE (opened_on <= %(end_date)s AND
              (closed_on IS NULL OR closed_on >= %(start_date)s ))
        GROUP BY ucr.supervisor_id, ucr.awc_id) ut
        WHERE ut.awc_id = agg_awc.awc_id and ut.supervisor_id=agg_awc.supervisor_id;
        """.format(
            tablename=self.temporary_tablename,
            ucr_tablename=self.get_table('static-person_cases_v3'),
            migration_table=AGG_MIGRATION_TABLE,
            availing_services_table=AGG_AVAILING_SERVICES_TABLE,
            seeking_services=(
                "CASE WHEN "
                "((agg_availing.is_registered IS DISTINCT FROM 0 OR agg_availing.registration_date::date >= %(start_date)s) AND "
                "(agg_migration.is_migrated IS DISTINCT FROM 1 OR agg_migration.migration_date::date >= %(start_date)s)) "
                "THEN 1 ELSE 0 END"
            )
        ), {
            'start_date': self.month_start,
            'end_date': self.month_end,
            'month_end_11yr': self.month_end_11yr,
            'month_start_15yr': self.month_start_15yr,
            'month_start_14yr': self.month_start_14yr,
            'month_end_15yr': self.month_end_15yr,
            'month_start_18yr': self.month_start_18yr,
        }

        yield """
        UPDATE "{tablename}" agg_awc SET
        cases_person_adolescent_girls_11_14_out_of_school = ut.girls_out_of_schoool
        FROM (
        select
            ucr.awc_id,
            ucr.supervisor_id,
            SUM(CASE WHEN ( (out_of_school or re_out_of_school) AND
                        (not admitted_in_school )) THEN 1 ELSE 0 END ) as girls_out_of_schoool
            from "{ucr_tablename}" ucr INNER JOIN
                 "{adolescent_girls_table}" adolescent_girls_table ON (
                    ucr.doc_id = adolescent_girls_table.person_case_id AND
                    ucr.supervisor_id = adolescent_girls_table.supervisor_id AND
                    adolescent_girls_table.month=%(start_date)s
                    )
                 LEFT JOIN
                 "{migration_table}" agg_migration ON (
                    ucr.doc_id = agg_migration.person_case_id AND
                    agg_migration.month = %(start_date)s AND
                    ucr.supervisor_id = agg_migration.supervisor_id
                 )
            WHERE (opened_on <= %(end_date)s AND
              (closed_on IS NULL OR closed_on >= %(start_date)s )) AND
              (agg_migration.is_migrated IS DISTINCT FROM 1 OR agg_migration.migration_date::date >= %(start_date)s) AND
              (%(month_end_11yr)s > dob AND %(month_start_14yr)s <= dob)
              GROUP BY ucr.awc_id, ucr.supervisor_id
        )ut
        where agg_awc.awc_id = ut.awc_id and ut.supervisor_id=agg_awc.supervisor_id;
        """.format(
            tablename=self.temporary_tablename,
            ucr_tablename=self.get_table('static-person_cases_v3'),
            adolescent_girls_table=AGG_ADOLESCENT_GIRLS_REGISTRATION_TABLE,
            migration_table=AGG_MIGRATION_TABLE
        ), {
            'start_date': self.month_start,
            'end_date': self.month_end,
            'month_end_11yr': self.month_end_11yr,
            'month_start_14yr': self.month_start_14yr,
        }

        yield """
        UPDATE "{tablename}" agg_awc SET
            cases_person_has_aadhaar_v2 = ut.child_has_aadhar,
            num_children_immunized = ut.num_children_immunized
        FROM ( 
        SELECT
            awc_id,
            supervisor_id,
            sum(has_aadhar_id) as child_has_aadhar,
            sum(immunization_in_month) AS num_children_immunized
        FROM "{child_health_monthly}"
        WHERE month = %(month)s and valid_in_month = 1
        GROUP BY awc_id, supervisor_id) ut
        WHERE ut.awc_id = agg_awc.awc_id and ut.supervisor_id = agg_awc.supervisor_id;
        """.format(
            tablename=self.temporary_tablename,
            child_health_monthly=self.child_temp_tablename,
        ), {
            "month": self.month_start
        }

        yield """
        UPDATE "{tablename}" agg_awc SET
            num_anc_visits = ut.num_anc_visits,
            cases_person_has_aadhaar_v2 = COALESCE(cases_person_has_aadhaar_v2, 0) + ut.ccs_has_aadhar
        FROM (
        SELECT
            awc_id,
            supervisor_id,
            sum(anc_in_month) AS num_anc_visits,
            sum(has_aadhar_id) AS ccs_has_aadhar
        FROM "{ccs_record_monthly}"
        WHERE month = %(month)s and (pregnant = 1 OR lactating = 1)
        GROUP BY awc_id, supervisor_id) ut
        WHERE ut.awc_id = agg_awc.awc_id and ut.supervisor_id = agg_awc.supervisor_id;
        """.format(
            tablename=self.temporary_tablename,
            ccs_record_monthly="ccs_record_monthly"
        ), {
            "month": self.month_start
        }

        yield """
        UPDATE "{tablename}" agg_awc SET
            usage_num_pse = ut.usage_num_pse,
            usage_num_gmp = ut.usage_num_gmp,
            usage_num_thr = ut.usage_num_thr,
            usage_num_hh_reg = ut.usage_num_hh_reg,
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
            usage_num_due_list_child_health = ut.usage_num_due_list_child_health,
            app_version = ut.app_version,
            commcare_version = ut.commcare_version
        FROM (
        SELECT
            awc_id,
            supervisor_id,
            month,
            sum(pse) AS usage_num_pse,
            sum(gmp) AS usage_num_gmp,
            sum(thr) AS usage_num_thr,
            sum(add_household) AS usage_num_hh_reg,
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
            LAST_VALUE(app_version) over w as app_version,
            LAST_VALUE(commcare_version) over w as commcare_version,
            CASE WHEN (
                sum(due_list_ccs) + sum(due_list_child) + sum(pse) + sum(gmp) + sum(thr)
                + sum(home_visit) + sum(add_pregnancy) + sum(add_household)
            ) >= 15 THEN 1 ELSE 0 END AS usage_awc_num_active,
            sum(due_list_ccs) AS usage_num_due_list_ccs,
            sum(due_list_child) AS usage_num_due_list_child_health
        FROM "{usage_table}"
        WHERE month = %(start_date)s GROUP BY awc_id, month, supervisor_id, app_version, commcare_version, form_date WINDOW w as (
                PARTITION BY awc_id, supervisor_id ORDER BY 
                form_date RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )) ut
        WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id AND ut.supervisor_id = agg_awc.supervisor_id;
        """.format(
            tablename=self.temporary_tablename,
            usage_table=get_table_name(self.domain, 'static-usage_forms'),
        ), {
            'start_date': self.month_start
        }

        yield """
        UPDATE "{tablename}" agg_awc SET
            infra_last_update_date = ut.infra_last_update_date,
            infra_type_of_building = ut.infra_type_of_building,
            infra_clean_water = ut.infra_clean_water,
            toilet_facility = ut.toilet_facility,
            type_toilet = ut.type_toilet,
            preschool_kit_available = ut.preschool_kit_available,
            preschool_kit_usable = ut.preschool_kit_usable,
            infra_functional_toilet = CASE WHEN ut.toilet_facility=1 THEN ut.infra_functional_toilet ELSE 0 END,
            infra_baby_weighing_scale = ut.infra_baby_weighing_scale,
            infra_adult_weighing_scale = ut.infra_adult_weighing_scale,
            infra_infant_weighing_scale = ut.infra_infant_weighing_scale,
            infra_cooking_utensils = ut.infra_cooking_utensils,
            infra_medicine_kits = ut.infra_medicine_kits,
            infra_adequate_space_pse = ut.infra_adequate_space_pse,
            electricity_awc = ut.electricity_awc,
            infantometer = ut.infantometer,
            stadiometer = ut.stadiometer,
            awc_with_gm_devices = ut.awc_with_gm_devices
        FROM (
            SELECT
                awc_id,
                supervisor_id,
                month,
                latest_time_end_processed::date AS infra_last_update_date,
                CASE
                  WHEN awc_building = 1 THEN 'pucca'
                  WHEN awc_building = 2 THEN 'semi_pucca'
                  WHEN awc_building = 3 THEN 'kuccha'
                  WHEN awc_building = 4 THEN 'partial_covered_space'
                ELSE NULL END AS infra_type_of_building,
                CASE WHEN source_drinking_water IN (1, 2, 3) THEN 1 ELSE 0 END AS infra_clean_water,
                toilet_facility,
                type_toilet,
                preschool_kit_available,
                preschool_kit_usable,
                toilet_functional AS infra_functional_toilet,
                baby_scale_usable AS infra_baby_weighing_scale,
                GREATEST(adult_scale_available, adult_scale_usable, 0) AS infra_adult_weighing_scale,
                GREATEST(
                    baby_scale_available, flat_scale_available, baby_scale_usable, 0
                ) AS infra_infant_weighing_scale,
                cooking_utensils_usable AS infra_cooking_utensils,
                medicine_kits_usable AS infra_medicine_kits,
                CASE WHEN adequate_space_pse = 1 THEN 1 ELSE 0 END AS infra_adequate_space_pse,
                electricity_awc AS electricity_awc,
                infantometer_usable AS infantometer,
                stadiometer_usable AS stadiometer,
                CASE WHEN GREATEST(adult_scale_available, adult_scale_usable, baby_scale_available,
                              flat_scale_available, baby_scale_usable,
                              infantometer_usable, stadiometer_usable, 0) > 0 THEN 1 ELSE 0 END as awc_with_gm_devices
            FROM icds_dashboard_infrastructure_forms
            WHERE month = %(start_date)s
        ) ut
        WHERE ut.awc_id = agg_awc.awc_id
        AND ut.supervisor_id = agg_awc.supervisor_id;
            -- could possibly add multicol indexes to make order by faster?
        """.format(
            tablename=self.temporary_tablename,
        ), {
            'start_date': self.month_start
        }

        yield """
         UPDATE "{tablename}" agg_awc SET num_awc_infra_last_update =
          CASE WHEN infra_last_update_date IS NOT NULL AND
             %(month_start_6m)s <= infra_last_update_date THEN 1 ELSE 0 END
        """.format(
            tablename=self.temporary_tablename
        ), {
            'month_start_6m': self.month_start_6m
        }

        yield """
            UPDATE "{tablename}" agg_awc SET
              state_is_test = ut.state_is_test,
              district_is_test = ut.district_is_test,
              block_is_test = ut.block_is_test,
              supervisor_is_test = ut.supervisor_is_test,
              awc_is_test = ut.awc_is_test
            FROM (
            SELECT
                doc_id as awc_id,
                supervisor_id as supervisor_id,
                MAX(state_is_test) as state_is_test,
                MAX(district_is_test) as district_is_test,
                MAX(block_is_test) as block_is_test,
                MAX(supervisor_is_test) as supervisor_is_test,
                MAX(awc_is_test) as awc_is_test
            FROM "{awc_location_tablename}"
            GROUP BY awc_id, supervisor_id) ut
            WHERE ut.awc_id = agg_awc.awc_id 
            AND ut.supervisor_id = agg_awc.supervisor_id AND (
                (
                  agg_awc.state_is_test IS NULL OR
                  agg_awc.district_is_test IS NULL OR
                  agg_awc.block_is_test IS NULL OR
                  agg_awc.supervisor_is_test IS NULL OR
                  agg_awc.awc_is_test IS NULL
                ) OR (
                  ut.state_is_test != agg_awc.state_is_test OR
                  ut.district_is_test != agg_awc.district_is_test OR
                  ut.block_is_test != agg_awc.block_is_test OR
                  ut.supervisor_is_test != agg_awc.supervisor_is_test OR
                  ut.awc_is_test != agg_awc.awc_is_test
                )
            );
        """.format(
            tablename=self.temporary_tablename,
            awc_location_tablename='awc_location',
        ), {
        }

        yield """
        UPDATE "{tablename}" agg_awc SET
            cases_child_health = ut.cases_child_health,
            cases_child_health_all = ut.cases_child_health_all,
            wer_weighed = ut.wer_weighed,
            wer_eligible = ut.wer_eligible,
            wer_eligible_0_2 = ut.wer_eligible_0_2,
            wer_weighed_0_2 = ut.wer_weighed_0_2,
            cases_person_beneficiary_v2 = ut.cases_child_health,
            thr_eligible_child = thr_eligible,
            thr_rations_21_plus_distributed_child = rations_21_plus_distributed
        FROM (
            SELECT
                awc_id,
                supervisor_id,
                month,
                sum(valid_in_month) AS cases_child_health,
                sum(valid_all_registered_in_month) AS cases_child_health_all,
                sum(nutrition_status_weighed) AS wer_weighed,
                sum(wer_eligible) AS wer_eligible,
                sum(CASE WHEN age_tranche in ('0','6','12','24') THEN wer_eligible ELSE 0 END) AS wer_eligible_0_2,
                sum(CASE WHEN age_tranche in ('0','6','12','24') THEN nutrition_status_weighed ELSE 0 END) AS wer_weighed_0_2,
                sum(thr_eligible) as thr_eligible,
                sum(rations_21_plus_distributed) as rations_21_plus_distributed
            FROM {agg_child_temp_tablename}
            WHERE month = %(start_date)s AND aggregation_level = 5 GROUP BY awc_id, month, supervisor_id
        ) ut
        WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id and ut.supervisor_id=agg_awc.supervisor_id;
        """.format(
            tablename=self.temporary_tablename,
            agg_child_temp_tablename=self.agg_child_temp_tablename,
        ), {
            'start_date': self.month_start
        }

        yield """
        DROP TABLE IF EXISTS "tmp_agg_awc_5";
        CREATE UNLOGGED TABLE "tmp_agg_awc_5" AS SELECT * FROM "{temporary_tablename}";
        INSERT INTO "{tablename}" (SELECT * FROM "tmp_agg_awc_5");
        DROP TABLE "tmp_agg_awc_5";
        """.format(
            tablename=self.tablename,
            temporary_tablename=self.temporary_tablename,
        ), {
        }

        yield """
        DROP TABLE IF EXISTS "tmp_home_visit";
        CREATE UNLOGGED TABLE "tmp_home_visit" AS SELECT
            ucr.awc_id,
            %(start_date)s AS month,
            SUM(COALESCE(agg_cf.valid_visits, 0)) AS valid_visits,
            sum(0.39) AS expected_visits
            FROM  "{ccs_record_case_ucr}" ucr
            LEFT OUTER JOIN "{agg_cf_table}" agg_cf ON (
                ucr.case_id = agg_cf.case_id AND
                agg_cf.month = %(start_date)s AND
                agg_cf.supervisor_id=ucr.supervisor_id
            )
            WHERE %(start_date)s - add BETWEEN 184 AND 548 AND (ucr.closed_on IS NULL OR
                date_trunc('month', ucr.closed_on)::DATE > %(start_date)s) AND
                date_trunc('month', ucr.opened_on) <= %(start_date)s
            GROUP BY ucr.awc_id;
        UPDATE "{tablename}" agg_awc SET
            cases_ccs_pregnant = ut.cases_ccs_pregnant,
            cases_ccs_lactating = ut.cases_ccs_lactating,
            cases_ccs_pregnant_all = ut.cases_ccs_pregnant_all,
            cases_ccs_lactating_all = ut.cases_ccs_lactating_all,
            num_mother_thr_21_days = ut.rations_21_plus_distributed,
            num_mother_thr_eligible = ut.thr_eligible,
            cases_person_beneficiary_v2 = (
                COALESCE(cases_person_beneficiary_v2, 0) + ut.cases_ccs_pregnant + ut.cases_ccs_lactating
            ),
            cases_ccs_lactating_reg_in_month = ut.lactating_registered_in_month,
            cases_ccs_pregnant_reg_in_month = ut.pregnant_registered_in_month,
            cases_ccs_lactating_all_reg_in_month = ut.lactating_all_registered_in_month,
            cases_ccs_pregnant_all_reg_in_month = ut.pregnant_all_registered_in_month,
            valid_visits = ut.valid_visits,
            expected_visits = CASE WHEN ut.valid_visits>ut.expected_visits
                THEN ut.valid_visits ELSE ut.expected_visits END
        FROM (
            SELECT
                agg_ccs_record_monthly.awc_id,
                agg_ccs_record_monthly.month,
                sum(agg_ccs_record_monthly.pregnant) AS cases_ccs_pregnant,
                sum(agg_ccs_record_monthly.lactating) AS cases_ccs_lactating,
                sum(agg_ccs_record_monthly.pregnant_all) AS cases_ccs_pregnant_all,
                sum(agg_ccs_record_monthly.lactating_all) AS cases_ccs_lactating_all,
                sum(agg_ccs_record_monthly.lactating_registered_in_month) as lactating_registered_in_month,
                sum(agg_ccs_record_monthly.pregnant_registered_in_month) as pregnant_registered_in_month,
                sum(agg_ccs_record_monthly.lactating_all_registered_in_month) as lactating_all_registered_in_month,
                sum(agg_ccs_record_monthly.pregnant_all_registered_in_month) as pregnant_all_registered_in_month,
                sum(agg_ccs_record_monthly.rations_21_plus_distributed) AS rations_21_plus_distributed,
                sum(agg_ccs_record_monthly.thr_eligible) AS thr_eligible,
                sum(agg_ccs_record_monthly.valid_visits) + COALESCE(home_visit.valid_visits, 0) AS valid_visits,
                sum(agg_ccs_record_monthly.expected_visits) +
                    COALESCE(home_visit.expected_visits, 0) AS expected_visits
            FROM agg_ccs_record_monthly
            LEFT OUTER JOIN "tmp_home_visit" home_visit ON agg_ccs_record_monthly.awc_id = home_visit.awc_id
                AND home_visit.month=agg_ccs_record_monthly.month
            WHERE agg_ccs_record_monthly.month = %(start_date)s AND aggregation_level = 5
            GROUP BY agg_ccs_record_monthly.awc_id, home_visit.valid_visits,
                home_visit.expected_visits, agg_ccs_record_monthly.month
        ) ut
        WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id;
        DROP TABLE "tmp_home_visit";
        """.format(
            tablename=self.tablename,
            ccs_record_case_ucr=self.get_table('static-ccs_record_cases'),
            agg_cf_table=AGG_CCS_RECORD_CF_TABLE,
        ), {
            'start_date': self.month_start
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
            ('wer_eligible_0_2',),
            ('wer_weighed_0_2',),
            ('cases_ccs_pregnant',),
            ('cases_ccs_lactating',),
            ('cases_child_health',),
            ('valid_visits',),
            ('expected_visits',),
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
            ('toilet_facility', 'NULL'),
            ('type_toilet', 'NULL'),
            ('preschool_kit_available',),
            ('preschool_kit_usable',),
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
            ('num_awcs_conducted_vhnd',),
            ('num_awcs_conducted_cbe',),
            ('cbe_conducted',),
            ('vhnd_conducted',),
            ('cases_household',),
            ('cases_person',),
            ('cases_person_all',),
            ('cases_ccs_pregnant_all',),
            ('cases_ccs_lactating_all',),
            ('cases_ccs_lactating_reg_in_month',),
            ('cases_ccs_pregnant_reg_in_month',),
            ('cases_ccs_lactating_all_reg_in_month',),
            ('cases_ccs_pregnant_all_reg_in_month',),
            ('num_mother_thr_21_days',),
            ('num_mother_thr_eligible',),
            ('cases_child_health_all',),
            ('cases_person_adolescent_girls_11_14',),
            ('cases_person_adolescent_girls_15_18',),
            ('cases_person_adolescent_girls_11_14_all',),
            ('cases_person_adolescent_girls_15_18_all',),
            ('cases_person_adolescent_girls_11_14_out_of_school',),
            ('cases_person_adolescent_girls_11_14_all_v2',),
            ('infra_infant_weighing_scale',),
            ('cases_person_referred', 'NULL'),
            ('awc_days_pse_conducted', 'NULL'),
            ('num_awc_infra_last_update',),
            ('cases_person_has_aadhaar_v2',),
            ('cases_person_beneficiary_v2',),
            ('thr_distribution_image_count',),
            ('thr_eligible_child',),
            ('thr_rations_21_plus_distributed_child',),
            ('electricity_awc', 'COALESCE(sum(electricity_awc), 0)'),
            ('infantometer', 'COALESCE(sum(infantometer), 0)'),
            ('stadiometer', 'COALESCE(sum(stadiometer), 0)'),
            ('awc_with_gm_devices', 'COALESCE(sum(awc_with_gm_devices), 0)'),
            ('num_anc_visits', 'COALESCE(sum(num_anc_visits), 0)'),
            ('num_children_immunized', 'COALESCE(sum(num_children_immunized), 0)'),
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
        ]

        def _transform_column(column_tuple):
            column = column_tuple[0]

            if len(column_tuple) == 2:
                agg_col = column_tuple[1]
                if isinstance(agg_col, str):
                    return column_tuple
                elif callable(agg_col):
                    return (column, agg_col(column))
            return column, 'SUM({})'.format(column)

        columns = list(map(_transform_column, columns))

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

        group_by.append("month")

        return """
            INSERT INTO "{to_tablename}" (
                {columns}
            ) (
                SELECT {calculations}
                FROM "{from_tablename}"
                WHERE {child_is_test} = 0
                GROUP BY {group_by}
            )
        """.format(
            from_tablename=self._tablename_func(aggregation_level + 1),
            to_tablename=self._tablename_func(aggregation_level),
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            group_by=", ".join(group_by),
            child_is_test=child_location
        )

    def create_temporary_table(self):
        return """
        CREATE UNLOGGED TABLE \"{table}\" (LIKE agg_awc INCLUDING INDEXES);
        SELECT create_distributed_table('{table}', 'supervisor_id');
        """.format(table=self.temporary_tablename)

    def drop_temporary_table(self):
        return """
        DROP TABLE IF EXISTS \"{table}\";
        """.format(table=self.temporary_tablename)
