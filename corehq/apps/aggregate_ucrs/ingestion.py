

"""
This module deals with data ingestion: populating the tables from other tables.
"""
from datetime import datetime
from sqlalchemy import func

from corehq.apps.userreports.sql import IndicatorSqlAdapter


def populate_aggregate_table_data(aggregate_table_adapter):
    """
    Seeds the database table with all initial data from the table adapter.
    """

    aggregate_table_definition = aggregate_table_adapter.config
    # get checkpoint
    last_update = get_last_aggregate_checkpoint(aggregate_table_definition)
    # get the earliest start date from the dataset
    start_date = get_aggregation_start_period(aggregate_table_definition, last_update)
    end_date = get_aggregation_end_period(aggregate_table_definition, last_update)


def get_last_aggregate_checkpoint(aggregate_table_definition):
    """
    Checkpoints indicate the last time the aggregation script successfully ran.
    Will be used to do partial ingestion.
    """
    # todo
    return None


def get_aggregation_start_period(aggregate_table_definition, last_update=None):
    return _get_aggregation_from_primary_table(
        aggregate_table_definition=aggregate_table_definition,
        column_id=aggregate_table_definition.aggregation_start_column,
        sqlalchemy_agg_fn=func.min,
        last_update=last_update,
    )


def get_aggregation_end_period(aggregate_table_definition, last_update=None):
    return _get_aggregation_from_primary_table(
        aggregate_table_definition=aggregate_table_definition,
        column_id=aggregate_table_definition.aggregation_end_column,
        sqlalchemy_agg_fn=func.max,
        last_update=last_update,
    ) or datetime.utcnow()


def _get_aggregation_from_primary_table(aggregate_table_definition, column_id, sqlalchemy_agg_fn, last_update):
    primary_data_source = aggregate_table_definition.data_source
    primary_data_source_adapter = IndicatorSqlAdapter(primary_data_source)
    with primary_data_source_adapter.session_helper.session_context() as session:
        primary_table = primary_data_source_adapter.get_table()
        aggregation_sql_column = primary_table.c[column_id]
        query = session.query(sqlalchemy_agg_fn(aggregation_sql_column))
        return session.execute(query).scalar()
