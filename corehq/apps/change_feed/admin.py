from django.contrib import admin

from corehq.apps.change_feed.models import PostgresPillowCheckpoint


@admin.register(PostgresPillowCheckpoint)
class PostgresPillowCheckpointAdmin(admin.ModelAdmin):
    list_display = [
        'pillow_id',
        'db_alias',
        'model',
        'update_sequence_id',
        'last_server_modified_on',
        'last_modified',
    ]
