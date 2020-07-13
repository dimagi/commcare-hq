from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_APP_VERSION_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter, transform_day_to_month, \
    get_app_version_temp_tablename
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    AggregationPartitionedHelper
)


class AppVersionAggregationDistributedHelper(AggregationPartitionedHelper):
    helper_key = 'usage-forms'
    ucr_data_source_id = 'static-usage_forms'
    tablename = AGG_APP_VERSION_TABLE

    def __init__(self, month):
        self.month = transform_day_to_month(month)
        self.prev_month_start = self.month - relativedelta(months=1)
        self.next_month_start = self.month + relativedelta(months=1)

    def aggregate(self, cursor):
        drop_query = self.drop_table_query()
        create_query = self.create_table_query()
        create_temp_query = self.create_temporary_table()
        drop_temp_query = self.drop_temporary_table()
        agg_query, agg_params = self.aggregation_query()
        index_queries = self.indexes()

        cursor.execute(drop_query)
        cursor.execute(create_query)
        cursor.execute(drop_temp_query)
        cursor.execute(create_temp_query)
        cursor.execute(agg_query, agg_params)

        for query in index_queries:
            cursor.execute(query)

        for i, query in enumerate(self.aggregation_queries()):
            cursor.execute(query)
        cursor.execute(drop_temp_query)

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
    def temporary_tablename(self):
        return get_app_version_temp_tablename()

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
            tablename=self.tablename,
        ), query_params

    def aggregation_query(self):
        ucr_query, ucr_query_params = self.data_from_ucr_query()
        query_params = {
            'previous_month': self.prev_month_start
        }
        query_params.update(ucr_query_params)

        return """
        INSERT INTO "{temporary_tablename}" (
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
             SELECT * FROM "{tablename}" where month = %(previous_month)s
             ) prev_month
            ON ucr.supervisor_id = prev_month.supervisor_id AND ucr.awc_id = prev_month.awc_id
            WHERE coalesce(ucr.month, %(start_date)s) = %(start_date)s
                AND coalesce(prev_month.month, %(previous_month)s) = %(previous_month)s
        )
        """.format(
            temporary_tablename=self.temporary_tablename,
            tablename=self.tablename,
            ucr_table_query=ucr_query
        ), query_params

    def indexes(self):
        return [
            f"""CREATE INDEX IF NOT EXISTS versions_awc_supervisor_idx
                ON "{self.tablename}" (month, awc_id, supervisor_id)
            """
        ]

    def create_temporary_table(self):
        return """
        CREATE UNLOGGED TABLE \"{table}\" (LIKE icds_dashboard_app_version);
        SELECT create_distributed_table('{table}', 'supervisor_id');
        """.format(table=self.temporary_tablename)

    def drop_temporary_table(self):
        return """
        DROP TABLE IF EXISTS \"{table}\";
        """.format(table=self.temporary_tablename)

    def aggregation_queries(self):
        return [
            """INSERT INTO "{new_tablename}" (SELECT * FROM "{tmp_tablename}")""".format(new_tablename=self.tablename, tmp_tablename=self.temporary_tablename),
            'DROP TABLE IF EXISTS "{monthly_tablename}"'.format(monthly_tablename=self.monthly_tablename),
            """ALTER TABLE "{new_tablename}" RENAME TO \"{tablename}\"""".format(new_tablename=self.tablename, tablename=self.monthly_tablename),
            """ALTER TABLE "{tablename}" ATTACH PARTITION "{monthly_tablename}" FOR VALUES IN ('{month}')""".format(monthly_tablename=self.monthly_tablename, month=self.month.strftime('%Y-%m-%d'), tablename=self.tablename),
        ]
