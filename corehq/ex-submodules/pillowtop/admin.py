from django.contrib import admin
from .models import *


class PillowCheckpointAdmin(admin.ModelAdmin):

    model = DjangoPillowCheckpoint
    list_display = [
        'checkpoint_id',
        'timestamp',
        'sequence',
    ]


admin.site.register(DjangoPillowCheckpoint, PillowCheckpointAdmin)


class KafkaCheckpointAdmin(admin.ModelAdmin):

    model = KafkaCheckpoint
    list_display = [
        'checkpoint_id',
        'topic',
        'partition',
        'offset',
        'last_modified',
    ]
    ordering = ('checkpoint_id', 'topic', 'partition')


admin.site.register(KafkaCheckpoint, KafkaCheckpointAdmin)
