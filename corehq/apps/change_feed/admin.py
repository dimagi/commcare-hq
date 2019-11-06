from django.contrib import admin

from corehq.apps.change_feed.models import PostgresPillowCheckpoint


@admin.register(PostgresPillowCheckpoint)
class PostgresPillowCheckpointAdmin(admin.ModelAdmin):
    list_display = [
        'pillow_id',
    ]
