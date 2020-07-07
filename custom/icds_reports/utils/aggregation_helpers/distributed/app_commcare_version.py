from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_APP_VERSION_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter, transform_day_to_month
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    BaseICDSAggregationDistributedHelper,
)


class AppVersionAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'usage-forms'
    ucr_data_source_id = 'static-usage_forms'
    aggregate_parent_table = AGG_APP_VERSION_TABLE

    def __init__(self, month):
        self.month = transform_day_to_month(month)
        self.prev_month_start = self.month - relativedelta(months=1)
        self.next_month_start = self.month + relativedelta(months=1)

    def aggregate(self, cursor):
        drop_query = self.drop_table_query()
        create_query = self.create_table_query()
        agg_query, agg_params = self.aggregation_query()
        index_queries = self.indexes()
        add_partition_query = self.add_partition_table__query()

        cursor.execute(drop_query)
        cursor.execute(create_query)
        cursor.execute(agg_query, agg_params)
        for query in index_queries:
            cursor.execute(query)

        cursor.execute(add_partition_query)

    def drop_table_query(self):
        return f"""
                DROP TABLE IF EXISTS "{self.tablename}"
            """

    def create_table_query(self):
        return f"""
            CREATE TABLE "{self.tablename}" (LIKE {self.aggregate_parent_table});
            SELECT create_distributed_table('{self.tablename}', 'supervisor_id');
        """

    @property
    def tablename(self):
        return "{}_{}".format(self.aggregate_parent_table, self.month.strftime("%Y-%m-%d"))

    def data_from_ucr_query(self):
        query_params = {
            "start_date": month_formatter(self.month),
            "end_date": month_formatter(self.next_month_start)
        }
        return """
            SELECT distinct
                awc_id,
                supervisor_id,
                %(start_date)s::DATE AS month,
                LAST_VALUE(app_version) over w as app_version,
                LAST_VALUE(commcare_version) over w as commcare_version
            FROM "{ucr_tablename}" WHERE
                form_date >= %(start_date)s AND form_date < %(end_date)s WINDOW w as (
                PARTITION BY awc_id, supervisor_id ORDER BY
                form_date RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table,
        ), query_params

    def aggregation_query(self):
        ucr_query, ucr_query_params = self.data_from_ucr_query()
        query_params = {
            'previous_month': self.prev_month_start
        }
        query_params.update(ucr_query_params)

        return """
        INSERT INTO "{tablename}" (
          awc_id, supervisor_id, month, app_version, commcare_version
        ) (
          SELECT
            ucr.awc_id AS awc_id,
            COALESCE(ucr.supervisor_id, prev_month.supervisor_id) AS supervisor_id,
            %(start_date)s::DATE AS month,
            COALESCE(ucr.app_version, prev_month.app_version) AS app_version,
            COALESCE(ucr.commcare_version, prev_month.commcare_version) as commcare_version
          FROM ({ucr_table_query}) ucr 
          FULL OUTER JOIN (
             SELECT * FROM "{prev_tablename}"
             ) prev_month
            ON ucr.supervisor_id = prev_month.supervisor_id AND ucr.awc_id = prev_month.awc_id
            WHERE coalesce(ucr.month, %(start_date)s) = %(start_date)s
                AND coalesce(prev_month.month, %(previous_month)s) = %(previous_month)s
        )
        """.format(
            tablename=self.aggregate_parent_table,
            ucr_table_query=ucr_query,
            prev_tablename=self.prev_tablename
        ), query_params

    def indexes(self):
        return [
            f"""CREATE INDEX IF NOT EXISTS versions_awc_supervisor_idx
                ON "{self.tablename}" (month, awc_id, supervisor_id)
            """
        ]

    def add_partition_table__query(self):
        return f"""
            ALTER TABLE "{self.aggregate_parent_table}" ATTACH PARTITION "{self.tablename}"
            FOR VALUES IN ('{month_formatter(self.month)}')
        """
