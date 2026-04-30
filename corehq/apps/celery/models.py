import json
import uuid

from django.db import models
from kombu.utils.json import JSONEncoder as KombuJSONEncoder
from kombu.utils.json import object_hook as kombu_object_hook


class KombuJSONDecoder(json.JSONDecoder):
    """
    Kombu doesn't define a JSONDecoder, but they do define an object_hook that
    is used by their loads implementation.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('object_hook', kombu_object_hook)
        super().__init__(*args, **kwargs)


class TaskRecord(models.Model):
    """
    Record to track a celery task/message prior to being processed by a worker.
    Once processed by a worker, whether it fails or succeeds,
    this record is deleted.
    """

    task_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    args = models.JSONField(encoder=KombuJSONEncoder, decoder=KombuJSONDecoder)
    kwargs = models.JSONField(
        encoder=KombuJSONEncoder, decoder=KombuJSONDecoder
    )
    date_created = models.DateTimeField(auto_now_add=True)
    # optional - captures issues queueing task
    error = models.TextField(blank=True, default='')

    def __str__(self):
        return f"<{self.name}> {self.task_id} {self.date_created}"
