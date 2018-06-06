

"""
This module deals with data ingestion: populating the tables from other tables.
"""
from collections import namedtuple
from datetime import datetime
import sqlalchemy

from corehq.apps.aggregate_ucrs.column_specs import ConstantColumnAdapter
from corehq.apps.aggregate_ucrs.date_utils import Month
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from dimagi.utils.parsing import json_format_date


AggregationParam = namedtuple('AggregationParam', 'name value mapped_column_id')


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
    assert end_date >= start_date
    start_month = current_month = Month.datetime_to_month(start_date).get_previous_month().get_previous_month().get_previous_month()
    end_month = Month.datetime_to_month(end_date)
    while current_month <= end_month:
        print ('processing data for {}'.format(current_month))
        start = AggregationParam(
            'agg_window_start', json_format_date(current_month.start), aggregate_table_definition.aggregation_start_column
        )
        end = AggregationParam(
            'agg_window_end', json_format_date(current_month.end), aggregate_table_definition.aggregation_end_column
        )
        populate_aggregate_table_data_for_time_period(
            aggregate_table_adapter, start, end,
        )
        current_month = current_month.get_next_month()


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
        sqlalchemy_agg_fn=sqlalchemy.func.min,
        last_update=last_update,
    )


def get_aggregation_end_period(aggregate_table_definition, last_update=None):
    return _get_aggregation_from_primary_table(
        aggregate_table_definition=aggregate_table_definition,
        column_id=aggregate_table_definition.aggregation_end_column,
        sqlalchemy_agg_fn=sqlalchemy.func.max,
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


def populate_aggregate_table_data_for_time_period(aggregate_table_adapter, start, end):
    """
    For a given period (start/end) - populate all data in the aggregate table associated
    with that period.
    """
    aggregation_params = {
        start.name: start.value,
        end.name: end.value,
    }
    primary_column_adapters = list(aggregate_table_adapter.config.get_primary_column_adapters())
    primary_table = IndicatorSqlAdapter(aggregate_table_adapter.config.data_source).get_table()
    all_query_columns = [pca.to_sqlalchemy_query_column(primary_table, aggregation_params) for pca in primary_column_adapters]
    for secondary_table in aggregate_table_adapter.config.secondary_tables.all():
        sqlalchemy_secondary_table = IndicatorSqlAdapter(secondary_table.data_source).get_table()
        for column_adapter in secondary_table.get_column_adapters():
            all_query_columns.append(column_adapter.to_sqlalchemy_query_column(sqlalchemy_secondary_table, aggregation_params))

    statement = sqlalchemy.select(
        all_query_columns
    )
    # apply join filters
    for secondary_table in aggregate_table_adapter.config.secondary_tables.all():
        sqlalchemy_secondary_table = IndicatorSqlAdapter(secondary_table.data_source).get_table()
        statement = statement.where(
            primary_table.c['doc_id'] == sqlalchemy_secondary_table.c[secondary_table.data_source_key]
        )

    # apply period start/end filters
    # to match, start should be before the end of the period and end should be after the start
    # this makes the first and last periods inclusive.
    statement = statement.where(primary_table.c[start.mapped_column_id] < end.value)
    statement = statement.where(sqlalchemy.or_(primary_table.c[end.mapped_column_id] == None,
                                               primary_table.c[end.mapped_column_id] >= start.value))
    for primary_column_adapter in primary_column_adapters:
        if not isinstance(primary_column_adapter, ConstantColumnAdapter):
            statement = statement.group_by(primary_column_adapter.to_sqlalchemy_query_column(primary_table, aggregation_params))

    print(statement)
    with aggregate_table_adapter.session_helper.session_context() as session:
        print(session.execute(statement).fetchall())


    # ideally this should be a single SQL script that takes the form:
    # insert into [aggregate_table] values (
    #   select p.id, month, [p.columns] [s1.columns] [s2.columns] from [primary_table] p (
    #     inner join [secondary_table] s1 on [s1.primary_col_id] = [primary_table].id
    #   group by p.id, month
    #   )
    # )
