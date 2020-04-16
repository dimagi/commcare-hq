from custom.icds_reports.const import BIHAR_API_MOTHER_DETAILS_TABLE, AGG_MIGRATION_TABLE
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper
from corehq.apps.userreports.util import get_table_name
from dateutil.relativedelta import relativedelta
from custom.icds_reports.utils.aggregation_helpers import transform_day_to_month, month_formatter
from corehq.apps.locations.models import SQLLocation


class BiharApiMotherDetailsHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'agg-bihar_api_mother_details'
    tablename = BIHAR_API_MOTHER_DETAILS_TABLE

    def __init__(self, month):
        self.month = transform_day_to_month(month)
        self.end_date = transform_day_to_month(month + relativedelta(months=1, seconds=-1))

    def aggregate(self, cursor):
        drop_query = self.drop_table_query()
        create_query = self.create_table_query()
        agg_query = self.aggregation_query()
        update_queries = self.update_queries()
        index_queries = self.indexes()
        add_partition_query = self.add_partition_table__query()

        cursor.execute(drop_query)
        cursor.execute(create_query)
        cursor.execute(agg_query)

        for query in update_queries:
            cursor.execute(query)
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
        month_end_string = month_formatter(self.end_date)
        person_case_ucr = get_table_name(self.domain, 'static-person_cases_v3')
        add_preg_ucr = get_table_name(self.domain, 'static-dashboard_add_pregnancy_form')
        pregnant_tasks_case_ucr = get_table_name(self.domain, 'static-pregnant-tasks_cases')

        columns = (
            ('state_id', 'person_list.state_id'),
            ('supervisor_id', 'person_list.supervisor_id'),
            ('month', f"'{month_start_string}'"),
            ('ccs_case_id', 'ccs_record.case_id'),
            ('person_id', 'person_list.doc_id'),
            ('household_id', 'person_list.household_case_id'),
            ('married', 'person_list.marital_status'),
            ('husband_name', 'person_list.husband_name'),
            ('last_preg_year', 'preg.last_preg'),
            ('last_preg_tt', 'person_list.last_preg_tt'),
            ('is_pregnant', 'person_list.is_pregnant'),
            ('tt_booster', 'ut.due_list_date_tt_booster'),

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
                FROM ccs_record_monthly ccs_record
                INNER JOIN "{person_case_ucr}" person_list ON (
                    person_list.doc_id = ccs_record.person_case_id AND
                    person_list.supervisor_id = ccs_record.supervisor_id
                )
                LEFT OUTER JOIN "{pregnant_tasks_case_ucr}" ut ON (
                ccs_record.case_id = ut.ccs_record_case_id AND
                ccs_record.supervisor_id = ut.supervisor_id
                )
                LEFT OUTER JOIN "{add_preg_ucr}" preg ON (
                ccs_record.case_id = preg.case_load_ccs_record0 AND
                ccs_record.supervisor_id = preg.supervisor_id AND
                preg.timeend <= '{month_end_string}'
                )
                WHERE
                    ccs_record.migration_status IS DISTINCT FROM 1 AND
                    ccs_record.month='{month_start_string}' AND
                    person_list.state_id='{self.bihar_state_id}'
              );
                """

    def update_queries(self):
        person_case_ucr = get_table_name(self.domain, 'static-person_cases_v3')

        yield f"""
        UPDATE "{self.monthly_tablename}" mother_details
            SET husband_id = person_list.doc_id
        FROM "{person_case_ucr}" person_list
        WHERE
            mother_details.household_id = person_list.household_case_id AND
            mother_details.husband_name = person_list.name AND
            mother_details.supervisor_id = person_list.supervisor_id
        """

    def indexes(self):
        return [
            f"""CREATE INDEX IF NOT EXISTS demographics_state_person_case_idx
                ON "{self.monthly_tablename}" (month, state_id, supervisor_id, ccs_case_id)
            """
        ]

    def add_partition_table__query(self):
        return f"""
            ALTER TABLE "{self.tablename}" ATTACH PARTITION "{self.monthly_tablename}"
            FOR VALUES IN ('{month_formatter(self.month)}')
        """
