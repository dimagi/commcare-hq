from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import DjangoPillowCheckpoint, KafkaCheckpoint


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
    list_filter = ('checkpoint_id', 'topic')
    ordering = ('checkpoint_id', 'topic', 'partition')


admin.site.register(KafkaCheckpoint, KafkaCheckpointAdmin)
