"""
Utility functions for importing AggregateTableDefinitions and associated models
from their config specifications.
"""
from uuid import UUID

from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition, PrimaryColumn, SecondaryTableDefinition, \
    SecondaryColumn, TimeAggregationDefinition


def import_aggregation_models_from_spec(spec):
    # todo: pretty sure this whole file can be completely replaced with DRF models...
    table_definition = _create_or_update_table_definition(spec)
    _update_primary_columns(spec, table_definition)
    _update_secondary_tables(spec, table_definition)
    return table_definition


def _create_or_update_table_definition(spec):
    try:
        table_definition = AggregateTableDefinition.objects.get(
            domain=spec.domain,
            table_id=spec.table_id,
        )
    except AggregateTableDefinition.DoesNotExist:
        table_definition = AggregateTableDefinition(
            domain=spec.domain,
            table_id=spec.table_id,
        )

    table_definition.display_name = spec.display_name
    table_definition.primary_data_source_id = UUID(spec.primary_table.data_source_id)
    table_definition.primary_data_source_key = spec.primary_table.key_column
    if spec.time_aggregation:
        db_aggregation_spec = table_definition.time_aggregation or TimeAggregationDefinition()
        db_aggregation_spec.aggregation_unit = spec.time_aggregation.unit
        db_aggregation_spec.start_column = spec.time_aggregation.start_column
        db_aggregation_spec.end_column = spec.time_aggregation.end_column
        db_aggregation_spec.save()
        table_definition.time_aggregation = db_aggregation_spec
    table_definition.save()
    return table_definition


def _update_primary_columns(spec, table_definition):
    found_column_ids = set()
    for column in spec.primary_table.columns:
        try:
            db_column = PrimaryColumn.objects.get(table_definition=table_definition, column_id=column.column_id)
        except PrimaryColumn.DoesNotExist:
            db_column = PrimaryColumn(table_definition=table_definition, column_id=column.column_id)
        db_column.column_type = column.type
        db_column.config_params = column.config_params
        db_column.save()
        found_column_ids.add(db_column.pk)

    # delete any columns that were removed
    table_definition.primary_columns.exclude(pk__in=list(found_column_ids)).delete()


def _update_secondary_tables(spec, table_definition):
    for secondary_table_spec in spec.secondary_tables:
        try:
            db_secondary_table = SecondaryTableDefinition.objects.get(
                table_definition=table_definition,
                data_source_id=secondary_table_spec.data_source_id
            )
        except SecondaryTableDefinition.DoesNotExist:
            db_secondary_table = SecondaryTableDefinition(
                table_definition=table_definition,
                data_source_id=secondary_table_spec.data_source_id
            )
        db_secondary_table.join_column_primary = secondary_table_spec.join_column_primary
        db_secondary_table.join_column_secondary = secondary_table_spec.join_column_secondary
        db_secondary_table.time_window_column = secondary_table_spec.time_window_column
        db_secondary_table.save()
        _update_secondary_columns(secondary_table_spec, db_secondary_table)


def _update_secondary_columns(secondary_table_spec, db_secondary_table):
    for column in secondary_table_spec.columns:
        try:
            db_column = SecondaryColumn.objects.get(
                table_definition=db_secondary_table,
                column_id=column.column_id,
            )
        except SecondaryColumn.DoesNotExist:
            db_column = SecondaryColumn(
                table_definition=db_secondary_table,
                column_id=column.column_id,
            )
        db_column.aggregation_type = column.aggregation_type
        db_column.config_params = column.config_params
        db_column.save()
