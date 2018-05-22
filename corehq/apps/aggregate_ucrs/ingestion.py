

"""
This module deals with data ingestion: populating the tables from other tables.
"""
from sqlalchemy import func

from corehq.apps.userreports.sql import IndicatorSqlAdapter


def populate_aggregate_table_data(aggregate_table_adapter):
    """
    Seeds the database table with all initial data from the table adapter.
    """

    print('initializing {}'.format(aggregate_table_adapter))
    aggregate_table_definition = aggregate_table_adapter.config
    # get checkpoint
    last_update = get_last_aggregate_checkpoint(aggregate_table_definition)

    start_date = get_aggregation_start_period(aggregate_table_definition, last_update)
    # get the earliest start date from the dataset


def get_last_aggregate_checkpoint(aggregate_table_definition):
    """
    Checkpoints indicate the last time the aggregation script successfully ran.
    Will be used to do partial ingestion.
    """
    # todo
    return None


def get_aggregation_start_period(aggregate_table_definition, last_update=None):
    primary_data_source = aggregate_table_definition.data_source
    aggregation_start_column = aggregate_table_definition.aggregation_start_column
    primary_data_source_adapter = IndicatorSqlAdapter(primary_data_source)
    with primary_data_source_adapter.session_helper.session_context() as session:
        primary_table = primary_data_source_adapter.get_table()
        aggregation_sql_column = primary_table.c[aggregation_start_column]
        query = session.query(func.min(aggregation_sql_column))
        return session.execute(query).scalar()
