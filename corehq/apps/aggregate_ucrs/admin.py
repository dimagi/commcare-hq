from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from . import models


class TimeAggregationDefinitionAdmin(admin.ModelAdmin):

    def get_changeform_initial_data(self, request):
        return {
            'start_column': 'opened_date',
            'end_column': 'closed_date',
        }


class PrimaryColumnInline(admin.TabularInline):
    model = models.PrimaryColumn
    extra = 0


class SecondaryTableInline(admin.TabularInline):
    model = models.SecondaryTableDefinition
    extra = 0


class AggregateTableDefinitionAdmin(admin.ModelAdmin):
    list_display = ['table_id', 'display_name', 'domain', 'date_created', 'date_modified']
    list_filter = ['domain', 'date_created', 'date_modified']
    inlines = [PrimaryColumnInline, SecondaryTableInline]


class PrimaryColumnAdmin(admin.ModelAdmin):
    list_display = ['column_id', 'column_type', 'table_definition']
    list_filter = ['column_type', 'table_definition']


class SecondaryColumnInline(admin.TabularInline):
    model = models.SecondaryColumn
    extra = 0


class SecondaryTableDefinitionAdmin(admin.ModelAdmin):
    list_display = ['table_definition', 'data_source_id', 'join_column_secondary', 'time_window_column']
    inlines = [SecondaryColumnInline]


class SecondaryColumnAdmin(admin.ModelAdmin):
    list_display = ['column_id', 'table_definition', 'aggregation_type']


admin.site.register(models.TimeAggregationDefinition, TimeAggregationDefinitionAdmin)
admin.site.register(models.AggregateTableDefinition, AggregateTableDefinitionAdmin)
admin.site.register(models.PrimaryColumn, PrimaryColumnAdmin)
admin.site.register(models.SecondaryTableDefinition, SecondaryTableDefinitionAdmin)
admin.site.register(models.SecondaryColumn, SecondaryColumnAdmin)
