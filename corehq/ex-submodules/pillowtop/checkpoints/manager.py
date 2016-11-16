from collections import namedtuple
from datetime import datetime
from pillowtop.exceptions import PillowtopCheckpointReset
from pillowtop.logger import pillow_logging
from pillowtop.models import DjangoPillowCheckpoint
from pillowtop.pillow.interface import ChangeEventHandler


DEFAULT_EMPTY_CHECKPOINT_SEQUENCE = '0'


def get_or_create_checkpoint(checkpoint_id):
    checkpoint, created = DjangoPillowCheckpoint.objects.get_or_create(
        checkpoint_id=checkpoint_id,
        defaults={
            'sequence': DEFAULT_EMPTY_CHECKPOINT_SEQUENCE,
            'timestamp': datetime.utcnow()
        })
    return checkpoint


def reset_checkpoint(checkpoint_id):
    checkpoint = get_or_create_checkpoint(checkpoint_id)
    checkpoint.old_sequence = checkpoint.sequence
    checkpoint.sequence = DEFAULT_EMPTY_CHECKPOINT_SEQUENCE
    checkpoint.timestamp = datetime.utcnow()
    checkpoint.save()


class PillowCheckpoint(object):

    def __init__(self, checkpoint_id):
        self.checkpoint_id = checkpoint_id
        self._last_checkpoint = None

    def get_or_create_wrapped(self, verify_unchanged=False):
        checkpoint = get_or_create_checkpoint(self.checkpoint_id)
        if (verify_unchanged and self._last_checkpoint and
                str(checkpoint.sequence) != str(self._last_checkpoint.sequence)):
            raise PillowtopCheckpointReset(u'Checkpoint {} expected seq {} but found {} in database.'.format(
                self.checkpoint_id, self._last_checkpoint.sequence, checkpoint.sequence,
            ))

        self._last_checkpoint = checkpoint
        return checkpoint

    def get_current_sequence_id(self):
        return get_or_create_checkpoint(self.checkpoint_id).sequence

    def update_to(self, seq):
        pillow_logging.info(
            "(%s) setting checkpoint: %s" % (self.checkpoint_id, seq)
        )
        checkpoint = self.get_or_create_wrapped(verify_unchanged=True)
        checkpoint.sequence = seq
        checkpoint.timestamp = datetime.utcnow()
        checkpoint.save()
        self._last_checkpoint = checkpoint

    def reset(self):
        reset_checkpoint(self.checkpoint_id)

    def touch(self, min_interval):
        """
        Update the checkpoint timestamp without altering the sequence.
        :param min_interval: minimum interval between timestamp updates
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


class PillowCheckpointEventHandler(ChangeEventHandler):

    def __init__(self, checkpoint, checkpoint_frequency, max_checkpoint_delay=300):
        """
        :param checkpoint: PillowCheckpoint object
        :param checkpoint_frequency: Number of changes between checkpoint updates
        :param max_checkpoint_delay: Max number of seconds between checkpoint updates
        """
        self.checkpoint = checkpoint
        self.checkpoint_frequency = checkpoint_frequency
        self.max_checkpoint_delay = max_checkpoint_delay
        self.last_update = datetime.utcnow()

    def should_update_checkpoint(self, context):
        frequency_hit = context.changes_seen % self.checkpoint_frequency == 0
        time_hit = (datetime.utcnow() - self.last_update).total_seconds() >= self.max_checkpoint_delay
        return context.do_set_checkpoint and (frequency_hit or time_hit)

    def fire_change_processed(self, change, context):
        if self.should_update_checkpoint(context):
            updated_to = change['seq']
            self.checkpoint.update_to(updated_to)


def get_default_django_checkpoint_for_legacy_pillow_class(pillow_class):
    return PillowCheckpoint(pillow_class.get_legacy_name())


def get_checkpoint_for_elasticsearch_pillow(pillow_id, index_info):
    checkpoint_id = u'{}-{}'.format(pillow_id, index_info.index)
    return PillowCheckpoint(checkpoint_id)
