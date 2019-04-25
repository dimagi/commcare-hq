"""
This module deals with data ingestion: populating the aggregate tables from other tables.
"""
from __future__ import absolute_import, unicode_literals
from collections import namedtuple
from datetime import datetime

import sqlalchemy
from sqlalchemy.dialects.postgresql import insert

from corehq.apps.aggregate_ucrs.aggregations import AGG_WINDOW_START_PARAM, AGG_WINDOW_END_PARAM, \
    TimePeriodAggregationWindow, get_time_period_class
from corehq.apps.userreports.util import get_indicator_adapter

AggregationParam = namedtuple('AggregationParam', 'name value mapped_column_id')
AggregationWindow = namedtuple('AggregationWindow', 'start end')


def populate_aggregate_table_data(aggregate_table_adapter):
    """
    Seeds the database table with all data from the table adapter.
    """
    aggregate_table_definition = aggregate_table_adapter.config
    # get checkpoint
    last_update = get_last_aggregate_checkpoint(aggregate_table_definition)
    for window in get_time_aggregation_windows(aggregate_table_definition, last_update):
        populate_aggregate_table_data_for_time_period(
            aggregate_table_adapter, window,
        )


def get_last_aggregate_checkpoint(aggregate_table_definition):
    """
    Checkpoints indicate the last time the aggregation script successfully ran.
    Will be used to do partial ingestion.
    """
    # todo
    return None


def get_time_aggregation_windows(aggregate_table_definition, last_update):
    if aggregate_table_definition.time_aggregation is None:
        # if there is no time aggregation just include a single window with no value
        yield None
    else:
        start_time = get_aggregation_start_period(aggregate_table_definition, last_update)
        end_time = get_aggregation_end_period(aggregate_table_definition, last_update)
        period_class = get_time_period_class(aggregate_table_definition.time_aggregation.aggregation_unit)
        current_window = TimePeriodAggregationWindow(period_class, start_time)
        end_window = TimePeriodAggregationWindow(period_class, end_time)
        while current_window <= end_window:
            yield AggregationWindow(
                start=AggregationParam(
                    name=AGG_WINDOW_START_PARAM,
                    value=current_window.start_param,
                    mapped_column_id=aggregate_table_definition.time_aggregation.start_column
                ),
                end=AggregationParam(
                    name=AGG_WINDOW_END_PARAM,
                    value=current_window.end_param,
                    mapped_column_id=aggregate_table_definition.time_aggregation.end_column
                )
            )
            current_window = current_window.next_window()


def get_aggregation_start_period(aggregate_table_definition, last_update=None):
    return _get_aggregation_from_primary_table(
        aggregate_table_definition=aggregate_table_definition,
        column_id=aggregate_table_definition.time_aggregation.start_column,
        sqlalchemy_agg_fn=sqlalchemy.func.min,
        last_update=last_update,
    )


def get_aggregation_end_period(aggregate_table_definition, last_update=None):
    value_from_db = _get_aggregation_from_primary_table(
        aggregate_table_definition=aggregate_table_definition,
        column_id=aggregate_table_definition.time_aggregation.end_column,
        sqlalchemy_agg_fn=sqlalchemy.func.max,
        last_update=last_update,
    )
    if not value_from_db:
        return datetime.utcnow()
    else:
        return max(value_from_db, datetime.utcnow())


def _get_aggregation_from_primary_table(aggregate_table_definition, column_id, sqlalchemy_agg_fn, last_update):
    primary_data_source = aggregate_table_definition.data_source
    primary_data_source_adapter = get_indicator_adapter(primary_data_source)
    with primary_data_source_adapter.session_helper.session_context() as session:
        primary_table = primary_data_source_adapter.get_table()
        aggregation_sql_column = primary_table.c[column_id]
        query = session.query(sqlalchemy_agg_fn(aggregation_sql_column))
        return session.execute(query).scalar()


def populate_aggregate_table_data_for_time_period(aggregate_table_adapter, window):
    """
    For a given period (start/end) - populate all data in the aggregate table associated
    with that period.
    """
    doing_time_aggregation = window is not None
    if doing_time_aggregation:
        aggregation_params = {
            window.start.name: window.start.value,
            window.end.name: window.end.value,
        }
    else:
        aggregation_params = {}

    primary_column_adapters = list(aggregate_table_adapter.config.get_primary_column_adapters())
    primary_table = get_indicator_adapter(aggregate_table_adapter.config.data_source).get_table()
    all_query_columns = [
        pca.to_sqlalchemy_query_column(primary_table, aggregation_params) for pca in primary_column_adapters
    ]
    for secondary_table in aggregate_table_adapter.config.secondary_tables.all():
        sqlalchemy_secondary_table = get_indicator_adapter(secondary_table.data_source).get_table()
        for column_adapter in secondary_table.get_column_adapters():
            all_query_columns.append(
                column_adapter.to_sqlalchemy_query_column(sqlalchemy_secondary_table, aggregation_params)
            )

    select_statement = sqlalchemy.select(
        all_query_columns
    )

    # now construct join
    select_table = primary_table
    for secondary_table in aggregate_table_adapter.config.secondary_tables.all():
        sqlalchemy_secondary_table = get_indicator_adapter(secondary_table.data_source).get_table()
        # apply join filters along with period start/end filters (if necessary) for related model
        join_conditions = [
            (primary_table.c[secondary_table.join_column_primary] ==
             sqlalchemy_secondary_table.c[secondary_table.join_column_secondary])
        ]
        if doing_time_aggregation:
            join_conditions.extend([
                sqlalchemy_secondary_table.c[secondary_table.time_window_column] >= window.start.value,
                sqlalchemy_secondary_table.c[secondary_table.time_window_column] < window.end.value
            ])
        select_table = select_table.outerjoin(
            sqlalchemy_secondary_table,
            sqlalchemy.and_(*join_conditions)
        )

    select_statement = select_statement.select_from(select_table)
    # apply period start/end filters for primary model
    # to match, start should be before the end of the period and end should be after the start
    # this makes the first and last periods inclusive.
    if doing_time_aggregation:
        select_statement = select_statement.where(
            primary_table.c[window.start.mapped_column_id] < window.end.value
        )
        select_statement = select_statement.where(
            sqlalchemy.or_(primary_table.c[window.end.mapped_column_id] == None,  # noqa this is sqlalchemy
                           primary_table.c[window.end.mapped_column_id] >= window.start.value))

    for primary_column_adapter in primary_column_adapters:
        if primary_column_adapter.is_groupable():
            select_statement = select_statement.group_by(
                primary_column_adapter.to_sqlalchemy_query_column(
                    primary_table, aggregation_params
                )
            )

    aggregate_table = aggregate_table_adapter.get_table()
    primary_key_columns = [
        aggregate_table.c[spec.column_id] for spec in primary_column_adapters if spec.is_primary_key()
    ]
    secondary_column_ids = [
        spec.column_id for spec in aggregate_table_adapter.config.get_column_adapters()
        if not spec.is_primary_key()
    ]
    insert_statement = insert(aggregate_table).from_select(
        aggregate_table.c, select_statement
    )
    insert_statement = insert_statement.on_conflict_do_update(
        index_elements=primary_key_columns,
        set_={
            k: insert_statement.excluded[k] for k in secondary_column_ids
        }

    )
    with aggregate_table_adapter.session_helper.session_context() as session:
        session.execute(insert_statement)
