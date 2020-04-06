
from custom.icds_reports.const import BIHAR_API_CHILD_VACCINE_TABLE
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper
from corehq.apps.userreports.util import get_table_name
from dateutil.relativedelta import relativedelta
from custom.icds_reports.utils.aggregation_helpers import transform_day_to_month, month_formatter, \
    get_child_health_tablename
from corehq.apps.locations.models import SQLLocation


class BiharApiChildVaccineHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'agg-bihar_api_child_vaccine'
    tablename = BIHAR_API_CHILD_VACCINE_TABLE

    def __init__(self, month):
        self.month = transform_day_to_month(month)
        self.end_date = transform_day_to_month(month + relativedelta(months=1, seconds=-1))

    def aggregate(self, cursor):
        drop_query = self.drop_table_query()
        create_query = self.create_table_query()
        agg_query = self.aggregation_query()
        index_queries = self.indexes()
        add_partition_query = self.add_partition_table__query()

        cursor.execute(drop_query)
        cursor.execute(create_query)
        cursor.execute(agg_query)
        for query in index_queries:
            cursor.execute(query)

        cursor.execute(add_partition_query)

    def drop_table_query(self):
        return f"""
                DROP TABLE IF EXISTS "{self.monthly_tablename}"
            """

    def create_table_query(self):
        return f"""
            CREATE TABLE "{self.monthly_tablename}" (LIKE {self.tablename});
            SELECT create_distributed_table('{self.monthly_tablename}', 'supervisor_id');
        """

    @property
    def monthly_tablename(self):
        return f"{self.tablename}_{month_formatter(self.month)}"

    @property
    def bihar_state_id(self):
        return SQLLocation.objects.get(name='Bihar', location_type__name='state').location_id

    def aggregation_query(self):
        month_start_string = month_formatter(self.month)
        month_end_string = month_formatter(self.month + relativedelta(months=1, seconds=-1))
        person_case_ucr = get_table_name(self.domain, 'static-person_cases_v3')
        ccs_case_ucr = get_table_name(self.domain, 'static-ccs_record_cases'),
        child_health_monthly = get_child_health_tablename(self.month)

        columns = (
            ('state_id', 'person_list.state_id'),
            ('district_id', 'person_list.district_id'),
            ('block_id', 'person_list.block_id'),
            ('supervisor_id', 'person_list.supervisor_id'),
            ('awc_id', 'person_list.awc_id'),
            ('month', f"'{month_start_string}'"),
            ('time_birth', 'person_list.time_birth'),
            ('child_alive', 'person_list.child_alive'),
            ('father_name', 'person_list.father_name'),
            ('mother_name', 'person_list.mother_name'),
            ("case_id", "child_health.case_id"),
            ('dob', 'person_list.dob'),
            ('doc_id', 'person_list.doc_id'),
            ('household_case_id', 'person_list.household_case_id'),
            ('delivery_nature', 'ccs_cases.delivery_nature'),
            ('term_days', 'CASE WHEN (person_list.dob-ccs_cases.lmp >z= 0) THEN 1 ELSE NULL END')
        )
        column_names = ", ".join([col[0] for col in columns])
        calculations = ", ".join([col[1] for col in columns])

        return f"""
                INSERT INTO "{self.monthly_tablename}" (
                    {column_names}
                )
                (
                SELECT
                {calculations}
                from "{child_health_monthly}" child_health
                LEFT JOIN "{person_case_ucr}" person_list ON (
                    person_list.doc_id = child_health.mother_id
                    AND person_list.supervisor_id = child_health.supervisor_id
                )
                LEFT JOIN "{ccs_case_ucr}" ccs_cases ON (
                    ccs_cases.person_case_id = child_health.mother_case_id
                    AND ccs_cases.supervisor_id = child_health.supervisor_id

                )
                WHERE 
                (
                    person_list.opened_on <= '{month_end_string}' AND
                    (person_list.closed_on IS NULL OR person_list.closed_on >= '{month_start_string}' )
                )
                
              );
                """

    def indexes(self):
        return [
            f"""CREATE INDEX IF NOT EXISTS demographics_state_person_case_idx
                ON "{self.monthly_tablename}" (month, state_id, person_id, supervisor_id, case_id)
            """
        ]

    def add_partition_table__query(self):
        return f"""
            ALTER TABLE "{self.tablename}" ATTACH PARTITION "{self.monthly_tablename}"
            FOR VALUES IN ('{month_formatter(self.month)}')
        """
