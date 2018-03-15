from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import SQLLocation, LocationType


class LocationTypeAdmin(admin.ModelAdmin):
    model = LocationType
    list_display = [
        'domain',
        'name',
        'code',
        'parent_type',
        'administrative',
    ]
    list_filter = [
        'domain',
        'administrative',
    ]


class LocationAdmin(admin.ModelAdmin):
    model = SQLLocation

    list_display = [
        'domain',
        'name',
        'location_type',
        'parent',
        'is_archived',
        'location_id',
        'supply_point_id'
    ]
    list_filter = [
        'domain',
        'is_archived',
    ]
    search_fields = [
        'name',
        'location_id',
        'supply_point_id',
    ]


admin.site.register(SQLLocation, LocationAdmin)
admin.site.register(LocationType, LocationTypeAdmin)
