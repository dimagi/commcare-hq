from datetime import datetime

from django.conf import settings
from django.db import transaction
from kafka.common import TopicPartition

from pillowtop.exceptions import PillowtopCheckpointReset
from pillowtop.logger import pillow_logging
from pillowtop.models import DjangoPillowCheckpoint, KafkaCheckpoint, kafka_seq_to_str, str_to_kafka_seq
from pillowtop.pillow.interface import ChangeEventHandler

MAX_CHECKPOINT_DELAY = 300
DELAY_SENTINEL = object()

DEFAULT_EMPTY_CHECKPOINT_SEQUENCE = {
    'text': '0',
    'json': '{}'
}


def get_or_create_checkpoint(checkpoint_id, sequence_format):
    checkpoint, created = DjangoPillowCheckpoint.objects.get_or_create(
        checkpoint_id=checkpoint_id,
        defaults={
            'sequence': DEFAULT_EMPTY_CHECKPOINT_SEQUENCE[sequence_format],
            'sequence_format': sequence_format,
            'timestamp': datetime.utcnow()
        })
    assert checkpoint.sequence_format == sequence_format
    return checkpoint


def reset_checkpoint(checkpoint_id, sequence_format):
    checkpoint = get_or_create_checkpoint(checkpoint_id, sequence_format)
    assert checkpoint.sequence_format == sequence_format
    checkpoint.old_sequence = checkpoint.sequence
    checkpoint.sequence = DEFAULT_EMPTY_CHECKPOINT_SEQUENCE[sequence_format]
    checkpoint.timestamp = datetime.utcnow()
    checkpoint.save()


class PillowCheckpoint(object):

    def __init__(self, checkpoint_id, sequence_format):
        self.checkpoint_id = checkpoint_id
        self.sequence_format = sequence_format
        self._last_checkpoint = None

    def get_or_create_wrapped(self, verify_unchanged=False):
        checkpoint = get_or_create_checkpoint(self.checkpoint_id, self.sequence_format)
        if (verify_unchanged and self._last_checkpoint and
                str(checkpoint.sequence) != str(self._last_checkpoint.sequence)):
            raise PillowtopCheckpointReset('Checkpoint {} expected seq {} but found {} in database.'.format(
                self.checkpoint_id, self._last_checkpoint.sequence, checkpoint.sequence,
            ))

        self._last_checkpoint = checkpoint
        return checkpoint

    def get_current_sequence_id(self):
        return get_or_create_checkpoint(self.checkpoint_id, self.sequence_format).sequence

    def update_to(self, seq, change=None):
        if isinstance(seq, int):
            seq = str(seq)

        pillow_logging.info(
            "(%s) setting checkpoint: %s" % (self.checkpoint_id, seq)
        )
        with transaction.atomic():
            checkpoint = self.get_or_create_wrapped(verify_unchanged=True)
            checkpoint.sequence = seq
            checkpoint.timestamp = datetime.utcnow()
            checkpoint.save()
        self._last_checkpoint = checkpoint

    def reset(self):
        reset_checkpoint(self.checkpoint_id, self.sequence_format)

    def touch(self, min_interval):
        """
        Update the checkpoint timestamp without altering the sequence.
        :param min_interval: minimum interval between timestamp updates

        :returns: Returns True if it updated the checkpoint, False otherwise
        """
        checkpoint = self.get_or_create_wrapped(verify_unchanged=True)
        now = datetime.utcnow()
        previous = self._last_checkpoint.timestamp if self._last_checkpoint else None
        do_update = True
        if previous:
            diff = now - previous
            do_update = diff.total_seconds() >= min_interval
        if do_update:
            checkpoint.timestamp = now
            checkpoint.save()
            return True
        return False


class KafkaPillowCheckpoint:

    def __init__(self, checkpoint_id, topics):
        self.checkpoint_id = checkpoint_id
        self.sequence_format = 'json'
        self.topics = topics
        self._get_checkpoints()

    def _get_checkpoints(self):
        return KafkaCheckpoint.get_or_create_for_checkpoint_id(self.checkpoint_id, self.topics)

    def get_or_create_wrapped(self, verify_unchanged=None):
        checkpoints = self._get_checkpoints()
        ret = {}
        if checkpoints:
            timestamp = checkpoints[0].last_modified
            for checkpoint in checkpoints:
                ret[TopicPartition(checkpoint.topic, checkpoint.partition)] = checkpoint.offset
                if checkpoint.last_modified > timestamp:
                    timestamp = checkpoint.last_modified
        else:
            timestamp = datetime.fromtimestamp(0)

        return WrappedCheckpoint(ret, timestamp)

    def get_current_sequence_as_dict(self):
        return {
            (checkpoint.topic, checkpoint.partition): checkpoint.offset
            for checkpoint in self._get_checkpoints()
        }

    def get_current_sequence_id(self):
        return kafka_seq_to_str(self.get_current_sequence_as_dict())

    def update_to(self, seq, change=None):
        if isinstance(seq, str):
            kafka_seq = str_to_kafka_seq(seq)
        else:
            kafka_seq = seq
            seq = kafka_seq_to_str(seq)

        pillow_logging.info(
            "(%s) setting checkpoint: %s" % (self.checkpoint_id, seq)
        )
        doc_modification_time = change.metadata.publish_timestamp if change else None

        with transaction.atomic():
            if kafka_seq:
                for topic_partition, offset in kafka_seq.items():
                    KafkaCheckpoint.objects.update_or_create(
                        checkpoint_id=self.checkpoint_id,
                        topic=topic_partition[0],
                        partition=topic_partition[1],
                        defaults={'offset': offset, 'doc_modification_time': doc_modification_time}
                    )

    def touch(self, min_interval):
        return False

    def reset(self):
        KafkaCheckpoint.objects.filter(checkpoint_id=self.checkpoint_id).delete()


class PillowCheckpointEventHandler(ChangeEventHandler):

    def __init__(self, checkpoint, checkpoint_frequency, checkpoint_callback=None):
        """
        :param checkpoint: PillowCheckpoint object
        :param checkpoint_frequency: Number of changes between checkpoint updates
        """
        # check settings to make it easy to override in tests
        self.max_checkpoint_delay = getattr(settings, 'PTOP_CHECKPOINT_DELAY_OVERRIDE', MAX_CHECKPOINT_DELAY)
        self.checkpoint = checkpoint
        self.checkpoint_frequency = checkpoint_frequency
        self.last_update = None
        self.last_log = None
        self.checkpoint_callback = checkpoint_callback

    def should_update_checkpoint(self, context):
        frequency_hit = context.changes_seen >= self.checkpoint_frequency
        time_hit = False
        if self.max_checkpoint_delay:
            if self.last_update is not None:
                seconds_since_last_update = (datetime.utcnow() - self.last_update).total_seconds()
                time_hit = seconds_since_last_update >= self.max_checkpoint_delay
            else:
                time_hit = True
        return frequency_hit or time_hit

    def get_new_seq(self, change):
        return change['seq']

    def update_checkpoint(self, change, context):
        if self.should_update_checkpoint(context):
            context.reset()
            self.checkpoint.update_to(self.get_new_seq(change))
            self.last_update = datetime.utcnow()
            if self.checkpoint_callback:
                self.checkpoint_callback.checkpoint_updated()
            return True
        elif self.last_log is None or (datetime.utcnow() - self.last_log).total_seconds() > 10:
            self.last_log = datetime.utcnow()
            pillow_logging.info("Heartbeat: %s", self.get_new_seq(change))

        return False


class WrappedCheckpoint(object):
    def __init__(self, kafka_seq, timestamp):
        self.kafka_seq = kafka_seq
        self.timestamp = timestamp
        self.sequence_format = 'json'

    @property
    def wrapped_sequence(self):
        return self.kafka_seq


def get_checkpoint_for_elasticsearch_pillow(pillow_id, index_name, topics):
    checkpoint_id = f'{pillow_id}-{index_name}'
    return KafkaPillowCheckpoint(checkpoint_id, topics)
