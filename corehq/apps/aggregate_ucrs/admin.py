from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from . import models


class AggregateTableDefinitionAdmin(admin.ModelAdmin):
    list_display = ['table_id', 'display_name', 'domain', 'date_created', 'date_modified']
    list_filter = ['domain', 'date_created', 'date_modified']


class PrimaryColumnAdmin(admin.ModelAdmin):
    list_display = ['column_id', 'column_type', 'table_definition']
    list_filter = ['column_type', 'table_definition']


class SecondaryTableDefinitionAdmin(admin.ModelAdmin):
    list_display = ['table_definition', 'data_source_id', 'join_column_secondary', 'time_window_column']


class SecondaryColumnAdmin(admin.ModelAdmin):
    list_display = ['column_id', 'table_definition', 'aggregation_type']


admin.site.register(models.TimeAggregationDefinition)
admin.site.register(models.AggregateTableDefinition, AggregateTableDefinitionAdmin)
admin.site.register(models.PrimaryColumn, PrimaryColumnAdmin)
admin.site.register(models.SecondaryTableDefinition, SecondaryTableDefinitionAdmin)
admin.site.register(models.SecondaryColumn, SecondaryColumnAdmin)
