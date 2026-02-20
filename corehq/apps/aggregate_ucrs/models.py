from django.db import models
from django.utils.translation import gettext_lazy as _

from jsonfield import JSONField

from corehq.apps.aggregate_ucrs.aggregations import (
    AGGREGATION_UNIT_CHOICE_MONTH,
    AGGREGATION_UNIT_CHOICE_WEEK,
)
from corehq.apps.aggregate_ucrs.column_specs import (
    PRIMARY_COLUMN_TYPE_CHOICES,
    SECONDARY_COLUMN_TYPE_CHOICES,
)
from corehq.sql_db.connections import UCR_ENGINE_ID

MAX_COLUMN_NAME_LENGTH = MAX_TABLE_NAME_LENGTH = 63


class TimeAggregationDefinition(models.Model):
    AGGREGATION_UNIT_CHOICES = (
        (AGGREGATION_UNIT_CHOICE_MONTH, _('Month')),
        (AGGREGATION_UNIT_CHOICE_WEEK, _('Week')),
    )
    aggregation_unit = models.CharField(max_length=10, choices=AGGREGATION_UNIT_CHOICES,
                                        default=AGGREGATION_UNIT_CHOICE_MONTH)
    start_column = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    end_column = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)


class AggregateTableDefinition(models.Model):
    """
    An aggregate table definition associated with multiple UCR data sources.
    Used to "join" data across multiple UCR tables.
    """
    domain = models.CharField(max_length=100)
    engine_id = models.CharField(default=UCR_ENGINE_ID, max_length=100)
    table_id = models.CharField(max_length=MAX_TABLE_NAME_LENGTH)
    display_name = models.CharField(max_length=100, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    # primary data source reference
    primary_data_source_id = models.UUIDField()  # id of DataSourceConfig
    primary_data_source_key = models.CharField(default='doc_id', max_length=MAX_COLUMN_NAME_LENGTH)

    time_aggregation = models.OneToOneField(TimeAggregationDefinition, null=True, blank=True,
                                            on_delete=models.CASCADE)

    class Meta:
        unique_together = ('domain', 'table_id')


class PrimaryColumn(models.Model):
    """
    A reference to a primary column in an aggregate table
    """
    table_definition = models.ForeignKey(AggregateTableDefinition, on_delete=models.CASCADE,
                                         related_name='primary_columns')
    column_id = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    column_type = models.CharField(max_length=20, choices=PRIMARY_COLUMN_TYPE_CHOICES)
    config_params = JSONField()


class SecondaryTableDefinition(models.Model):
    """
    A reference to a secondary table in an aggregate table
    """
    table_definition = models.ForeignKey(AggregateTableDefinition, on_delete=models.CASCADE,
                                         related_name='secondary_tables')
    data_source_id = models.UUIDField()
    join_column_primary = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    join_column_secondary = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    time_window_column = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH, null=True, blank=True)


class SecondaryColumn(models.Model):
    """
    An aggregate column in an aggregate data source.
    """
    table_definition = models.ForeignKey(SecondaryTableDefinition, on_delete=models.CASCADE,
                                         related_name='columns')
    column_id = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    aggregation_type = models.CharField(max_length=20, choices=SECONDARY_COLUMN_TYPE_CHOICES)
    config_params = JSONField()
