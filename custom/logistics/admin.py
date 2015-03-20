from django.contrib import admin
from .models import *


class MigrationCheckpointAdmin(admin.ModelAdmin):
    model = MigrationCheckpoint
    list_display = [
        'domain',
        'date',
        'start_date',
    ]


class StockDataCheckpointAdmin(admin.ModelAdmin):
    model = StockDataCheckpoint
    list_display = [
        'domain',
        'date',
        'start_date',
        'location',
    ]


admin.site.register(MigrationCheckpoint, MigrationCheckpointAdmin)
admin.site.register(StockDataCheckpoint, StockDataCheckpointAdmin)
