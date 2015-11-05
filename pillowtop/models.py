from django.db import models


class DjangoPillowCheckpoint(models.Model):

    checkpoint_id = models.CharField(primary_key=True, max_length=100)
    sequence = models.TextField()
    timestamp = models.DateTimeField(auto_now=True)
    old_sequence = models.TextField(null=True, blank=True)

    @staticmethod
    def to_dict(instance):
        """
        Return a dictionary that looks like the Couch-based implementation of these.
        """
        return {
            '_id': instance.checkpoint_id,
            'seq': instance.sequence,
            'timestamp': instance.timestamp.isoformat(),
            'old_seq': instance.old_sequence,
        }

    @staticmethod
    def from_dict(checkpoint_dict):
        """
        Create a checkpoint from a dictionary that looks like the
        Couch-based implementation of these.
        """
        return DjangoPillowCheckpoint(
            checkpoint_id=checkpoint_dict['pk'],
            sequence=checkpoint_dict['seq'],
            old_sequence=checkpoint_dict.get('old_seq', None)
        )
