from collections import namedtuple
from datetime import datetime
from pillowtop.exceptions import PillowtopCheckpointReset
from pillowtop.logger import pillow_logging
from pillowtop.models import DjangoPillowCheckpoint
from pillowtop.pillow.interface import ChangeEventHandler


DEFAULT_EMPTY_CHECKPOINT_SEQUENCE = '0'

DocGetOrCreateResult = namedtuple('DocGetOrCreateResult', ['document', 'created'])


def get_or_create_checkpoint(checkpoint_id):
    created = False
    try:
        checkpoint = DjangoPillowCheckpoint.objects.get(checkpoint_id=checkpoint_id)
    except DjangoPillowCheckpoint.DoesNotExist:
        checkpoint = DjangoPillowCheckpoint.objects.create(
            checkpoint_id=checkpoint_id,
            sequence=DEFAULT_EMPTY_CHECKPOINT_SEQUENCE,
            timestamp=datetime.utcnow(),
        )
        created = True
    return DocGetOrCreateResult(checkpoint, created)


def reset_checkpoint(checkpoint_id):
    checkpoint = get_or_create_checkpoint(checkpoint_id).document
    checkpoint.old_sequence = checkpoint.sequence
    checkpoint.sequence = DEFAULT_EMPTY_CHECKPOINT_SEQUENCE
    checkpoint.timestamp = datetime.utcnow()
    checkpoint.save()


class PillowCheckpoint(object):

    def __init__(self, checkpoint_id):
        self.checkpoint_id = checkpoint_id
        self._last_checkpoint = None

    def get_or_create_wrapped(self, verify_unchanged=False):
        result = get_or_create_checkpoint(self.checkpoint_id)
        checkpoint, created = result
        if (verify_unchanged and self._last_checkpoint and
                str(checkpoint.sequence) != str(self._last_checkpoint.sequence)):
            raise PillowtopCheckpointReset(u'Checkpoint {} expected seq {} but found {} in database.'.format(
                self.checkpoint_id, self._last_checkpoint.sequence, checkpoint.sequence,
            ))

        self._last_checkpoint = checkpoint
        return result

    def get_current_sequence_id(self):
        return get_or_create_checkpoint(self.checkpoint_id).document.sequence

    def update_to(self, seq):
        pillow_logging.info(
            "(%s) setting checkpoint: %s" % (self.checkpoint_id, seq)
        )
        checkpoint = self.get_or_create_wrapped(verify_unchanged=True).document
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
        checkpoint = self.get_or_create_wrapped(verify_unchanged=True).document
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

    def __init__(self, checkpoint, checkpoint_frequency):
        self.checkpoint = checkpoint
        self.checkpoint_frequency = checkpoint_frequency

    def fire_change_processed(self, change, context):
        if context.changes_seen % self.checkpoint_frequency == 0 and context.do_set_checkpoint:
            self.checkpoint.update_to(change['seq'])


def get_default_django_checkpoint_for_legacy_pillow_class(pillow_class):
    return PillowCheckpoint(pillow_class.get_legacy_name())
