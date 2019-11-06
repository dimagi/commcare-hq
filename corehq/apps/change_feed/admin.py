from django.contrib import admin

from corehq.apps.change_feed.models import (
    PostgresPillowCheckpoint,
    PostgresPillowSettings,
)


@admin.register(PostgresPillowCheckpoint)
class PostgresPillowCheckpointAdmin(admin.ModelAdmin):
    list_display = [
        'pillow_id',
    ]


@admin.register(PostgresPillowSettings)
class PostgresPillowSettingsAdmin(admin.ModelAdmin):
    pass
