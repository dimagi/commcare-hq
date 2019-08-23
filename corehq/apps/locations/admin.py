from django.contrib import admin
from .models import SQLLocation, LocationType, LocationRelation


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


class LocationRelationAdmin(admin.ModelAdmin):
    model = LocationRelation

    list_display = [
        'id',
        'location_a',
        'location_b',
    ]
    readonly_fields = ('location_a', 'location_b')
    search_fields = [
        'location_a__domain',
        'location_a__name',
        'location_b__domain',
        'location_b__name',
    ]


admin.site.register(SQLLocation, LocationAdmin)
admin.site.register(LocationType, LocationTypeAdmin)
admin.site.register(LocationRelation, LocationRelationAdmin)
