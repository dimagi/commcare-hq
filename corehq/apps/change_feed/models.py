from django.db import models


class PostgresPillowCheckpoint(models.Model):
    pillow_id = models.TextField()
    db_alias = models.TextField()
    model = models.TextField()
    remainder = models.IntegerField()

    batch_size = models.IntegerField(default=100)
    update_sequence_id = models.BigIntegerField()
    last_server_modified_on = models.DateTimeField()
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            ('pillow_id', 'db_alias', 'model', 'remainder'),
        )
