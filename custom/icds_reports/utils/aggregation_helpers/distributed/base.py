import hashlib
import logging

from django.db import transaction

from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.routers import db_for_read_write
from custom.icds_reports.const import DASHBOARD_DOMAIN
from custom.icds_reports.utils.aggregation_helpers import (
    AggregationHelper,
    month_formatter,
    transform_day_to_month,
)

logger = logging.getLogger(__name__)


class BaseICDSAggregationDistributedHelper(AggregationHelper):
    """Defines an interface for aggregating data from UCRs to specific tables
    for the dashboard.

    All aggregate tables are partitioned by state and month

    Attributes:
        ucr_data_source_id - The UCR data source that contains the raw data to aggregate
        aggregate_parent_table - The parent table defined in models.py that will contain aggregate data
    """
    ucr_data_source_id = None
    aggregate_parent_table = None

    def __init__(self, state_id, month):
        self.state_id = state_id
        self.month = transform_day_to_month(month)

    @property
    def domain(self):
        # Currently its only possible for one domain to have access to the ICDS dashboard per env
        return DASHBOARD_DOMAIN

    @property
    def ucr_tablename(self):
        return get_table_name(self.domain, self.ucr_data_source_id)

    def aggregate(self, cursor):
        raise NotImplementedError

    def drop_table_query(self):
        raise NotImplementedError

    def data_from_ucr_query(self):
        """Returns (SQL query, query parameters) from the UCR data table that
        puts data in the form expected by the aggregate table
        """
        raise NotImplementedError

    def aggregate_query(self):
        """Returns (SQL query, query parameters) that will aggregate from a UCR
        source to an aggregate table.
        """
        raise NotImplementedError


class StateBasedAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    def aggregate(self, cursor):
        delete_query, delete_params = self.delete_old_data_query()
        agg_query, agg_params = self.aggregation_query()

        logger.info(f'Deleting {self.helper_key} for {self.month} and state {self.state_id}')
        cursor.execute(delete_query, delete_params)
        logger.info(f'Starting aggregation for {self.helper_key} month {self.month} and state {self.state_id}')
        cursor.execute(agg_query, agg_params)
        logger.info(f'Finished aggregation for {self.helper_key} month {self.month} and state {self.state_id}')

    def delete_old_data_query(self):
        return (
            f'DELETE FROM "{self.aggregate_parent_table}" WHERE month=%(month)s AND state_id = %(state)s',
            {'month': month_formatter(self.month), 'state': self.state_id}
        )


class StateBasedAggregationPartitionedHelper(BaseICDSAggregationDistributedHelper):
    """Helper for tables that reside on Citus master and are partitioned into one tables per month and state

    Attributes:
        aggregate_child_table_prefix - The prefix for tables that inherit from the parent table
    """
    aggregate_child_table_prefix = None

    def aggregate(self, cursor):
        drop_query = self.drop_table_query()
        curr_month_query, curr_month_params = self.create_table_query()
        agg_query, agg_param = self.aggregate_query()

        logger.info(f'Deleting {self.helper_key} for {self.month} and state {self.state_id}')
        cursor.execute(drop_query)
        logger.info(f'Creating table for {self.helper_key} month {self.month} and state {self.state_id}')
        cursor.execute(curr_month_query, curr_month_params)
        logger.info(f'Starting aggregation for {self.helper_key} month {self.month} and state {self.state_id}')
        cursor.execute(agg_query, agg_param)
        logger.info(f'Finished aggregation for {self.helper_key} month {self.month} and state {self.state_id}')

    def generate_child_tablename(self, month=None):
        month = month or self.month
        month_string = month_formatter(month)
        hash_for_table = hashlib.md5((self.state_id + month_string).encode('utf-8')).hexdigest()[8:]
        return self.aggregate_child_table_prefix + hash_for_table

    def drop_table_query(self):
        tablename = self.generate_child_tablename(self.month)
        return 'DROP TABLE IF EXISTS "{tablename}"'.format(tablename=tablename)

    def create_table_query(self, month=None):
        month = month or self.month
        month_string = month_formatter(month)
        tablename = self.generate_child_tablename(month)

        return """
        CREATE TABLE IF NOT EXISTS "{child_tablename}" (
            CHECK (month = %(month_string)s AND state_id = %(state_id)s),
            LIKE "{parent_tablename}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
        ) INHERITS ("{parent_tablename}")
        """.format(
            parent_tablename=self.aggregate_parent_table,
            child_tablename=tablename,
        ), {
            "month_string": month_string,
            "state_id": self.state_id
        }


class AggregationPartitionedHelper(BaseICDSAggregationDistributedHelper):
    """Helper for tables that reside on Citus master and are partitioned into one tables per month
    """
    staging_tablename = None
    base_tablename = None
    monthly_tablename = None
    model = None

    def __init__(self, month):
        self.month = transform_day_to_month(month)

    def aggregate(self, cursor):
        staging_queries = self.staging_queries()
        update_queries = self.update_queries()
        rollup_queries = [self.rollup_query(i) for i in range(4, 0, -1)]

        logger.info(f"Creating staging table for {self.helper_key}")
        cursor.execute(f"DROP TABLE IF EXISTS {self.staging_tablename}")
        cursor.execute(f"CREATE UNLOGGED TABLE {self.staging_tablename} (LIKE {self.base_tablename})")

        logger.info(f"Inserting inital data into staging table for {self.helper_key}")
        for staging_query, params in staging_queries:
            cursor.execute(staging_query, params)

        logger.info(f"Updating data into staging table for {self.helper_key}")
        for query, params in update_queries:
            cursor.execute(query, params)

        logger.info(f"Rolling up data into staging table for {self.helper_key}")
        for query in rollup_queries:
            cursor.execute(query)

        logger.info(f"Creating new table for {self.helper_key} {self.month}")
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS "{self.monthly_tablename}" (
            CHECK (month = DATE '{self.month.strftime('%Y-%m-01')}')
        )
        INHERITS ({self.base_tablename})
        """)

        logger.info(f"Creating indexes for {self.helper_key} {self.month}")
        for index_query in self.indexes():
            cursor.execute(index_query)

        db_alias = db_for_read_write(self.model)
        with transaction.atomic(using=db_alias):
            logger.info(f"Dropping legacy tables for {self.helper_key} {self.month}")
            for i in range(1, 6):
                cursor.execute(f'DROP TABLE IF EXISTS "{self._legacy_tablename_func(i)}"')

            logger.info(f"Removing current data for {self.helper_key} {self.month}")
            cursor.execute(f'DELETE FROM "{self.monthly_tablename}"')

            logger.info(f"Inserting new data for {self.helper_key} {self.month}")
            cursor.execute(f"""
            INSERT INTO "{self.monthly_tablename}" (
                SELECT * FROM "{self.staging_tablename}"
                ORDER BY aggregation_level, state_id, district_id, block_id, supervisor_id, awc_id
            )
            """)

        logger.info(f"Dropping staging table for {self.helper_key} {self.month}")
        cursor.execute(f"DROP TABLE IF EXISTS {self.staging_tablename}")
        logger.info(f"Finished aggregation for {self.helper_key} {self.month}")

    def _legacy_tablename_func(self, agg_level):
        return "{}_{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"), agg_level)
