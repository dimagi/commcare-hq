from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django.db import models
from kafka.common import TopicPartition
import six

SEQUENCE_FORMATS = (
    ('text', 'text'),
    ('json', 'json'),
)


def str_to_kafka_seq(seq):
    seq = json.loads(seq)
    # deconstruct tuple keys
    marshaled_seq = {}
    for key, val in seq.items():
        topic, partition = key.split(',')
        marshaled_seq[TopicPartition(topic, int(partition))] = val
    return marshaled_seq


def kafka_seq_to_str(seq):
    # json doesn't like tuples as keys
    seq = {'{},{}'.format(*key): val for key, val in seq.items()}
    json_seq = json.dumps(seq)
    if six.PY2:
        json_seq = json_seq.decode('utf-8')
    return json_seq


class DjangoPillowCheckpoint(models.Model):

    checkpoint_id = models.CharField(primary_key=True, max_length=100)
    sequence = models.TextField()
    timestamp = models.DateTimeField(auto_now=True)
    old_sequence = models.TextField(null=True, blank=True)
    sequence_format = models.CharField(max_length=20, choices=SEQUENCE_FORMATS, default='text')

    @property
    def wrapped_sequence(self):
        if self.sequence_format == 'json':
            return str_to_kafka_seq(self.sequence)
        else:
            return self.sequence

    class Meta(object):
        app_label = "pillowtop"

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


class KafkaCheckpoint(models.Model):
    checkpoint_id = models.CharField(max_length=126, db_index=True)
    topic = models.CharField(max_length=126)
    partition = models.IntegerField()
    offset = models.BigIntegerField()
    doc_modification_time = models.DateTimeField(null=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta(object):
        unique_together = ('checkpoint_id', 'topic', 'partition')

    @classmethod
    def get_or_create_for_checkpoint_id(cls, checkpoint_id, topics):
        num_already_created = (
            cls.objects
            .filter(checkpoint_id=checkpoint_id, topic__in=topics)
            .distinct('topic', 'partition')
            .values_list('topic', 'partition').count()
        )

        if num_already_created == 0:
            _create_checkpoints_from_kafka(checkpoint_id, topics)

        return list(cls.objects.filter(checkpoint_id=checkpoint_id, topic__in=topics))


def _create_checkpoints_from_kafka(checkpoint_id, topics):
    # breaks pillowtop separation from hq
    from corehq.apps.change_feed.topics import get_multi_topic_first_available_offsets

    all_offsets = get_multi_topic_first_available_offsets(topics)

    for tp, offset in all_offsets.items():
        KafkaCheckpoint.objects.get_or_create(
            checkpoint_id=checkpoint_id,
            topic=tp[0], partition=tp[1],
            defaults={"offset": 0}
        )
