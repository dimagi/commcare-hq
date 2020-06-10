
from custom.icds_reports.const import BIHAR_API_DEMOGRAPHICS_TABLE, AGG_MIGRATION_TABLE
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper
from corehq.apps.userreports.util import get_table_name
from dateutil.relativedelta import relativedelta
from custom.icds_reports.utils.aggregation_helpers import transform_day_to_month, month_formatter
from corehq.apps.locations.models import SQLLocation


class BiharApiDemographicsHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'agg-bihar_api_demographics'
    tablename = BIHAR_API_DEMOGRAPHICS_TABLE
    months_required = 3

    def __init__(self, month):
        self.month = transform_day_to_month(month)
        self.next_month_start = month + relativedelta(months=1)
        self.person_case_ucr = get_table_name(self.domain, 'static-person_cases_v3')
        self.household_ucr = get_table_name(self.domain, 'static-household_cases')
        self.current_month_table = self.monthly_tablename()

    def aggregate(self, cursor):
        drop_older_table = self.drop_old_tables_query()
        drop_query = self.drop_table_query()
        create_query = self.create_table_query()
        agg_query = self.aggregation_query()
        update_queries = self.update_queries()
        add_partition_query = self.add_partition_table__query()

        cursor.execute(drop_older_table)
        cursor.execute(drop_query)
        cursor.execute(create_query)
        cursor.execute(agg_query)

        for query in update_queries:
            cursor.execute(query)

        cursor.execute(add_partition_query)

    def drop_old_tables_query(self):
        month = self.month - relativedelta(months=self.months_required)

        return f"""
            DROP TABLE IF EXISTS "{self.monthly_tablename(month)}"
        """

    def drop_table_query(self):
        return f"""
                DROP TABLE IF EXISTS "{self.current_month_table}"
            """

    def create_table_query(self):
        return f"""
            CREATE TABLE "{self.current_month_table}" (LIKE {self.tablename});
            SELECT create_distributed_table('{self.current_month_table}', 'supervisor_id');
        """

    def monthly_tablename(self, month=None):
        if not month:
            month = self.month

        return f"{self.tablename}_{month_formatter(month)}"

    def get_state_id_from_state_name(self, state_name):
        return SQLLocation.objects.get(name=state_name, location_type__name='state').location_id

    @property
    def bihar_state_id(self):
        return self.get_state_id_from_state_name('Bihar')

    def aggregation_query(self):
        month_start_string = month_formatter(self.month)

        columns = (
            ('state_id', 'person_list.state_id'),
            ('district_id', 'person_list.district_id'),
            ('block_id', 'person_list.block_id'),
            ('supervisor_id', 'person_list.supervisor_id'),
            ('awc_id', 'person_list.awc_id'),
            ('month', f"'{month_start_string}'"),
            ('person_id', 'person_list.doc_id'),
            ('person_name', 'person_list.name'),
            ('has_adhaar', 'CASE WHEN person_list.aadhar_date is not null THEN 1 ELSE 0 END'),
            ('bank_account_number', 'person_list.bank_account_number'),
            ('ifsc_code', 'person_list.ifsc_code'),
            ('age_at_reg', 'person_list.age_at_reg'),
            ('dob', 'person_list.dob'),
            ('gender', 'person_list.sex'),
            ('blood_group', 'person_list.blood_group'),
            ('disabled', 'person_list.disabled'),
            ('disability_type', 'person_list.disability_type'),
            ('referral_status', 'person_list.referral_status'),
            ('migration_status', 'migration_tab.is_migrated'),
            ('resident', 'person_list.resident'),
            ('registered_status', 'person_list.registered_status'),
            ('rch_id', 'person_list.rch_id'),
            ('mcts_id', 'person_list.mcts_id'),
            ('phone_number', 'person_list.phone_number'),
            ('date_death', 'person_list.date_death'),
            ('site_death', 'person_list.site_death'),
            ('closed_on', 'person_list.closed_on'),
            ('reason_closure', 'person_list.reason_closure'),
            ('married', 'person_list.marital_status'),
            ('husband_name', 'person_list.husband_name'),
            ('last_preg_tt', 'person_list.last_preg_tt'),
            ('is_pregnant', 'person_list.is_pregnant'),
            ('household_id', 'hh_list.doc_id'),
            ('household_name', 'hh_list.name'),
            ('hh_reg_date', 'hh_list.hh_reg_date'),
            ('hh_num', 'hh_list.hh_num'),
            ('hh_gps_location', 'hh_list.hh_gps_location'),
            ('hh_caste', 'hh_list.hh_caste'),
            ('hh_bpl_apl', 'hh_list.hh_bpl_apl'),
            ('hh_minority', 'hh_list.hh_minority'),
            ('hh_religion', 'hh_list.hh_religion'),
            ('time_birth', 'person_list.time_birth'),
            ('child_alive', 'person_list.child_alive'),
            ('father_name', 'person_list.father_name'),
            ('mother_name', 'person_list.mother_name'),
            ('private_admit', 'person_list.private_admit'),
            ('primary_admit', 'person_list.primary_admit'),
            ('date_last_private_admit', 'person_list.date_last_private_admit '),
            ('date_return_private', 'person_list.date_return_private'),
            ('out_of_school_status', 'person_list.is_oos'),
            ('last_class_attended_ever', 'person_list.last_class_attended_ever'),
            ('last_reported_fever_date', 'person_list.last_reported_fever_date'),
            ('age_marriage', 'person_list.age_marriage'),
            ('last_referral_date', 'person_list.last_referral_date'),
            ('referral_health_problem', 'person_list.referral_health_problem'),
            ('referral_reached_date', 'person_list.referral_reached_date'),
            ('referral_reached_facility', 'person_list.referral_reached_facility'),
            ('migrate_date', 'migration_tab.migration_date'),
            ('was_oos_ever', 'person_list.was_oos_ever')
        )
        column_names = ", ".join([col[0] for col in columns])
        calculations = ", ".join([col[1] for col in columns])

        return f"""
                INSERT INTO "{self.current_month_table}" (
                    {column_names}
                )
                (
                SELECT
                {calculations}
                from "{self.person_case_ucr}" person_list
                LEFT JOIN "{AGG_MIGRATION_TABLE}" migration_tab ON (
                    person_list.doc_id = migration_tab.person_case_id AND
                    person_list.supervisor_id = migration_tab.supervisor_id AND
                    migration_tab.month='{month_start_string}'
                )
                LEFT JOIN "{self.household_ucr}" hh_list ON (
                    person_list.household_case_id = hh_list.doc_id AND
                    person_list.supervisor_id = hh_list.supervisor_id
                )
                WHERE 
                (
                    person_list.opened_on < '{self.next_month_start}' AND
                    (person_list.closed_on IS NULL OR person_list.closed_on >= '{month_start_string}' )
                ) AND
                (
                    migration_tab.is_migrated is distinct from 1 OR
                    migration_tab.migration_date>='{month_start_string}'
                ) AND person_list.state_id='{self.bihar_state_id}'
                
              );
                """

    def update_queries(self):
        person_case_ucr = get_table_name(self.domain, 'static-person_cases_v3')

        yield f"""
        UPDATE "{self.current_month_table}" demographics_details
            SET husband_id = person_list.doc_id
        FROM "{person_case_ucr}" person_list
        WHERE
            demographics_details.household_id = person_list.household_case_id AND
            demographics_details.husband_name = person_list.name AND
            demographics_details.supervisor_id = person_list.supervisor_id AND
            person_list.state_id='{self.bihar_state_id}'
        """

        yield f"""
            UPDATE  "{self.current_month_table}" bihar_demographics
                SET father_id = person_list.doc_id
                    FROM "{self.person_case_ucr}" person_list
                    WHERE
                        bihar_demographics.household_id = person_list.household_case_id AND
                        bihar_demographics.father_name = person_list.name AND 
                        bihar_demographics.supervisor_id = person_list.supervisor_id AND
                        person_list.state_id='{self.bihar_state_id}'
            """

    def add_partition_table__query(self):
        return f"""
            ALTER TABLE "{self.tablename}" ATTACH PARTITION "{self.current_month_table}"
            FOR VALUES IN ('{month_formatter(self.month)}')
        """
