from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import models
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField

from corehq.sql_db.connections import UCR_ENGINE_ID


MAX_COLUMN_NAME_LENGTH = MAX_TABLE_NAME_LENGTH = 63


class AggregateTableDefinition(models.Model):
    """
    An aggregate table definition associated with multiple UCR data sources.
    Used to "join" data across multiple UCR tables.
    """
    AGGREGATION_UNIT_CHOICE_MONTH = 'month'
    AGGREGATION_UNIT_CHOICES = (
        (AGGREGATION_UNIT_CHOICE_MONTH, _('Month')),
    )
    domain = models.CharField(max_length=100)
    engine_id = models.CharField(default=UCR_ENGINE_ID, max_length=100)
    table_id = models.CharField(max_length=MAX_TABLE_NAME_LENGTH)
    display_name = models.CharField(max_length=100, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    # primary data source reference
    primary_data_source_id = models.UUIDField()  # id of DataSourceConfig
    primary_data_source_key = models.CharField(default='doc_id', max_length=MAX_COLUMN_NAME_LENGTH)

    # aggregation config
    aggregation_unit = models.CharField(max_length=10, choices=AGGREGATION_UNIT_CHOICES,
                                        default=AGGREGATION_UNIT_CHOICE_MONTH)
    aggregation_start_column = models.CharField(default='opened_date', max_length=MAX_COLUMN_NAME_LENGTH)
    aggregation_end_column = models.CharField(default='closed_date', max_length=MAX_COLUMN_NAME_LENGTH)


class PrimaryColumn(models.Model):
    """
    A reference to a primary column in an aggregate table
    """
    PRIMARY_COLUMN_TYPE_REFERENCE = 'reference'
    PRIMARY_COLUMN_TYPE_CONSTANT = 'constant'
    PRIMARY_COLUMN_TYPE_CHOICES = (
        (PRIMARY_COLUMN_TYPE_REFERENCE, _('Reference')),
        (PRIMARY_COLUMN_TYPE_CONSTANT, _('Reference')),
    )
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
    data_source = models.UUIDField()
    data_source_key = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    aggregation_column = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)


class SecondaryColumn(models.Model):
    """
    An aggregate column in an aggregate data source.
    """
    AGGREGATE_COLUMN_TYPE_SUM = 'sum'
    AGGREGATE_COLUMN_TYPE_CHOICES = (
        (AGGREGATE_COLUMN_TYPE_SUM, _('Sum')),
    )
    table_definition = models.ForeignKey(SecondaryTableDefinition, on_delete=models.CASCADE,
                                         related_name='columns')
    column_id = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    aggregation_type = models.CharField(max_length=10, choices=AGGREGATE_COLUMN_TYPE_CHOICES)
    config_params = JSONField()
