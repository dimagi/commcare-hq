from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import models
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from memoized import memoized

from corehq.apps.aggregate_ucrs.aggregations import AGGREGATION_UNIT_CHOICE_MONTH, AGGREGATION_UNIT_CHOICE_WEEK
from corehq.apps.aggregate_ucrs.column_specs import PRIMARY_COLUMN_TYPE_CHOICES, PrimaryColumnAdapter, \
    SecondaryColumnAdapter, SECONDARY_COLUMN_TYPE_CHOICES, IdColumnAdapter, MonthColumnAdapter, WeekColumnAdapter
from corehq.apps.userreports.models import get_datasource_config, SQLSettings, AbstractUCRDataSource
from corehq.apps.userreports.sql.util import decode_column_name
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

    def get_column_adapter(self):
        if self.aggregation_unit == AGGREGATION_UNIT_CHOICE_MONTH:
            return MonthColumnAdapter()
        if self.aggregation_unit == AGGREGATION_UNIT_CHOICE_WEEK:
            return WeekColumnAdapter()
        else:
            raise Exception(
                'Aggregation units apart from {} are not supported'.format(
                    ', '.join(u[0] for u in self.AGGREGATION_UNIT_CHOICES)
                )
            )

    def __str__(self):
        return '{} {}: {}-{}'.format(
            self.aggregatetabledefinition if hasattr(self, 'aggregatetabledefinition') else _('no table'),
            self.aggregation_unit, self.start_column, self.end_column)


class AggregateTableDefinition(models.Model, AbstractUCRDataSource):
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

    def __str__(self):
        return '{} ({})'.format(self.display_name or self.table_id, self.domain)

    @property
    def mirrored_engine_ids(self):
        return []

    @property
    def data_source_id(self):
        return self.id

    @property
    @memoized
    def data_source(self):
        return get_datasource_config(self.primary_data_source_id.hex, self.domain)[0]

    @property
    def sql_settings(self):
        # this is necessary for compatibility with IndicatorSqlAdapter
        # todo: will probably need to make this configurable at some point
        return SQLSettings()

    @property
    def sql_column_indexes(self):
        # this is necessary for compatibility with IndicatorSqlAdapter
        # todo: will probably need to make this configurable at some point
        return []

    def get_columns(self):
        for adapter in self.get_column_adapters():
            yield adapter.to_ucr_column_spec()

    def get_column_adapters(self):
        for primary_adapter in self.get_primary_column_adapters():
            yield primary_adapter
        for secondary_table in self.secondary_tables.all():
            for column_adapter in secondary_table.get_column_adapters():
                yield column_adapter

    def _get_id_column_adapater(self):
        return IdColumnAdapter()

    def get_primary_column_adapters(self):
        yield self._get_id_column_adapater()
        if self.time_aggregation:
            yield self.time_aggregation.get_column_adapter()
        for primary_column in self.primary_columns.all():
            yield PrimaryColumnAdapter.from_db_column(primary_column)

    @property
    def pk_columns(self):
        columns = []
        for col in self.get_columns():
            if col.is_primary_key:
                column_name = decode_column_name(col)
                columns.append(column_name)
        return columns


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

    def __str__(self):
        return '{} - {}:{}'.format(self.table_definition, self.data_source_id, self.join_column_secondary)

    @property
    @memoized
    def data_source(self):
        return get_datasource_config(self.data_source_id.hex, self.table_definition.domain)[0]

    def get_column_adapters(self):
        for secondary_column in self.columns.all():
            yield SecondaryColumnAdapter.from_db_column(secondary_column)


class SecondaryColumn(models.Model):
    """
    An aggregate column in an aggregate data source.
    """
    table_definition = models.ForeignKey(SecondaryTableDefinition, on_delete=models.CASCADE,
                                         related_name='columns')
    column_id = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    aggregation_type = models.CharField(max_length=20, choices=SECONDARY_COLUMN_TYPE_CHOICES)
    config_params = JSONField()
