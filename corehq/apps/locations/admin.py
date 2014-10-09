from django.contrib import admin
from .models import SQLLocation


class LocationAdmin(admin.ModelAdmin):
    model = SQLLocation

    list_display = [
        'domain',
        'name',
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
