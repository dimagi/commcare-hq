
from custom.icds_reports.const import CHILD_VACCINE_TABLE
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.utils.aggregation_helpers import transform_day_to_month, month_formatter, \
    get_child_health_tablename


class ChildVaccineHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'agg-child-vaccines'
    tablename = CHILD_VACCINE_TABLE

    def __init__(self, month):
        self.month = transform_day_to_month(month)

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

    def aggregation_query(self):
        month_start_string = month_formatter(self.month)
        child_tasks_ucr = get_table_name(self.domain, 'static-child_tasks_cases')
        child_health_monthly = get_child_health_tablename(self.month)

        columns = (
            ('state_id', 'child_tasks.state_id'),
            ('supervisor_id', 'child_tasks.supervisor_id'),
            ('child_health_case_id', 'child_tasks.child_health_case_id'),
            ("month", self.month.strftime("'%Y-%m-%d'")),
            ("due_list_date_1g_dpt_1", "child_tasks.due_list_date_1g_dpt_1"),
            ("due_list_date_2g_dpt_2", "child_tasks.due_list_date_2g_dpt_2"),
            ("due_list_date_3g_dpt_3", "child_tasks.due_list_date_3g_dpt_3"),
            ("due_list_date_5g_dpt_booster", "child_tasks.due_list_date_5g_dpt_booster"),
            ("due_list_date_5g_dpt_booster1", "child_tasks.due_list_date_5g_dpt_booster1"),
            ("due_list_date_7gdpt_booster_2", "child_tasks.due_list_date_7gdpt_booster_2"),
            ("due_list_date_0g_hep_b_0", "child_tasks.due_list_date_0g_hep_b_0"),
            ("due_list_date_1g_hep_b_1", "child_tasks.due_list_date_1g_hep_b_1"),
            ("due_list_date_2g_hep_b_2", "child_tasks.due_list_date_2g_hep_b_2"),
            ("due_list_date_3g_hep_b_3", "child_tasks.due_list_date_3g_hep_b_3"),
            ("due_list_date_3g_ipv", "child_tasks.due_list_date_3g_ipv"),
            ("due_list_date_4g_je_1", "child_tasks.due_list_date_4g_je_1"),
            ("due_list_date_5g_je_2", "child_tasks.due_list_date_5g_je_2"),
            ("due_list_date_5g_measles_booster", "child_tasks.due_list_date_5g_measles_booster"),
            ("due_list_date_4g_measles", "child_tasks.due_list_date_4g_measles"),
            ("due_list_date_0g_opv_0", "child_tasks.due_list_date_0g_opv_0"),
            ("due_list_date_1g_opv_1", "child_tasks.due_list_date_1g_opv_1"),
            ("due_list_date_2g_opv_2", "child_tasks.due_list_date_2g_opv_2"),
            ("due_list_date_3g_opv_3", "child_tasks.due_list_date_3g_opv_3"),
            ("due_list_date_5g_opv_booster", "child_tasks.due_list_date_5g_opv_booster"),
            ("due_list_date_1g_penta_1", "child_tasks.due_list_date_1g_penta_1"),
            ("due_list_date_2g_penta_2", "child_tasks.due_list_date_2g_penta_2"),
            ("due_list_date_3g_penta_3", "child_tasks.due_list_date_3g_penta_3"),
            ("due_list_date_1g_rv_1", "child_tasks.due_list_date_1g_rv_1"),
            ("due_list_date_2g_rv_2", "child_tasks.due_list_date_2g_rv_2"),
            ("due_list_date_3g_rv_3", "child_tasks.due_list_date_3g_rv_3"),
            ("due_list_date_4g_vit_a_1", "child_tasks.due_list_date_4g_vit_a_1"),
            ("due_list_date_5g_vit_a_2", "child_tasks.due_list_date_5g_vit_a_2"),
            ("due_list_date_6g_vit_a_3", "child_tasks.due_list_date_6g_vit_a_3"),
            ("due_list_date_6g_vit_a_4", "child_tasks.due_list_date_6g_vit_a_4"),
            ("due_list_date_6g_vit_a_5", "child_tasks.due_list_date_6g_vit_a_5"),
            ("due_list_date_6g_vit_a_6", "child_tasks.due_list_date_6g_vit_a_6"),
            ("due_list_date_6g_vit_a_7", "child_tasks.due_list_date_6g_vit_a_7"),
            ("due_list_date_6g_vit_a_8", "child_tasks.due_list_date_6g_vit_a_8"),
            ("due_list_date_7g_vit_a_9", "child_tasks.due_list_date_7g_vit_a_9"),
            ("due_list_date_anc_1", "child_tasks.due_list_date_anc_1"),
            ("due_list_date_anc_2", "child_tasks.due_list_date_anc_2"),
            ("due_list_date_anc_3", "child_tasks.due_list_date_anc_3"),
            ("due_list_date_anc_4", "child_tasks.due_list_date_anc_4"),
            ("due_list_date_tt_1", "child_tasks.due_list_date_tt_1"),
            ("due_list_date_tt_2", "child_tasks.due_list_date_tt_2"),
            ("due_list_date_tt_booster", "child_tasks.due_list_date_tt_booster"),
            ("due_list_date_1g_bcg", "child_tasks.due_list_date_1g_bcg")
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
                FROM "{child_tasks_ucr}" child_tasks
                INNER JOIN "{child_health_monthly}" child_health ON
                child_tasks.child_health_case_id = child_health.case_id AND 
                child_tasks.supervisor_id = child_health.supervisor_id
                WHERE 
                (
                    child_health.month = '{month_start_string}'
                    
                )
              );
                """

    def indexes(self):
        return [
            f"""CREATE INDEX IF NOT EXISTS vaccines_state_child_health_case_idx
                ON "{self.monthly_tablename}" (month, state_id, child_health_case_id)
            """
        ]

    def add_partition_table__query(self):
        return f"""
            ALTER TABLE "{self.tablename}" ATTACH PARTITION "{self.monthly_tablename}"
            FOR VALUES IN ('{month_formatter(self.month)}')
        """
