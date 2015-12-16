from collections import namedtuple
from datetime import datetime
from dateutil import parser
import pytz
from pillowtop.checkpoints.util import get_formatted_current_timestamp
from pillowtop.dao.django import DjangoDocumentStore
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.exceptions import PillowtopCheckpointReset
from pillowtop.logger import pillow_logging
from pillowtop.models import DjangoPillowCheckpoint
from pillowtop.pillow.interface import ChangeEventHandler


DocGetOrCreateResult = namedtuple('DocGetOrCreateResult', ['document', 'created'])


class PillowCheckpointManager(object):

    def __init__(self, dao):
        self._dao = dao

    def get_or_create_checkpoint(self, checkpoint_id):
        created = False
        try:
            checkpoint_doc = self._dao.get_document(checkpoint_id)
        except DocumentNotFoundError:
            checkpoint_doc = {'seq': '0', 'timestamp': get_formatted_current_timestamp()}
            self._dao.save_document(checkpoint_id, checkpoint_doc)
            created = True
        return DocGetOrCreateResult(checkpoint_doc, created)

    def reset_checkpoint(self, checkpoint_id):
        checkpoint_doc = self.get_or_create_checkpoint(checkpoint_id).document
        checkpoint_doc['old_seq'] = checkpoint_doc['seq']
        checkpoint_doc['seq'] = '0'
        checkpoint_doc['timestamp'] = get_formatted_current_timestamp()
        self._dao.save_document(checkpoint_id, checkpoint_doc)

    def update_checkpoint(self, checkpoint_id, checkpoint_doc):
        self._dao.save_document(checkpoint_id, checkpoint_doc)


class PillowCheckpoint(object):

    def __init__(self, dao, checkpoint_id):
        self._manager = PillowCheckpointManager(dao=dao)
        self.checkpoint_id = checkpoint_id
        self._last_checkpoint = None

    def get_or_create(self, verify_unchanged=False):
        result = self._manager.get_or_create_checkpoint(self.checkpoint_id)
        checkpoint, created = result
        if (verify_unchanged and self._last_checkpoint and
                    str(checkpoint['seq']) != str(self._last_checkpoint['seq'])):
            raise PillowtopCheckpointReset(u'Checkpoint {} expected seq {} but found {} in database.'.format(
                self.checkpoint_id, self._last_checkpoint['seq'], checkpoint['seq'],
            ))

        self._last_checkpoint = checkpoint
        return result

    def update_to(self, seq):
        pillow_logging.info(
            "(%s) setting checkpoint: %s" % (self.checkpoint_id, seq)
        )
        checkpoint = self.get_or_create(verify_unchanged=True).document
        checkpoint['seq'] = seq
        checkpoint['timestamp'] = get_formatted_current_timestamp()
        self._manager.update_checkpoint(self.checkpoint_id, checkpoint)
        self._last_checkpoint = checkpoint

    def reset(self):
        return self._manager.reset_checkpoint(self.checkpoint_id)

    def touch(self, min_interval):
        """
        Update the checkpoint timestamp without altering the sequence.
        :param min_interval: minimum interval between timestamp updates
        """
        checkpoint = self.get_or_create(verify_unchanged=True).document
        now = datetime.now(tz=pytz.UTC)
        previous = self._last_checkpoint.get('timestamp')
        do_update = True
        if previous:
            diff = now - parser.parse(previous).replace(tzinfo=pytz.UTC)
            do_update = diff.total_seconds() >= min_interval
        if do_update:
            checkpoint['timestamp'] = now.isoformat()
            self._manager.update_checkpoint(self.checkpoint_id, checkpoint)


class PillowCheckpointEventHandler(ChangeEventHandler):

    def __init__(self, checkpoint, checkpoint_frequency):
        self.checkpoint = checkpoint
        self.checkpoint_frequency = checkpoint_frequency

    def fire_change_processed(self, change, context):
        if context.changes_seen % self.checkpoint_frequency == 0 and context.do_set_checkpoint:
            self.checkpoint.update_to(change['seq'])


def get_django_checkpoint_store():
    return DjangoDocumentStore(
        DjangoPillowCheckpoint, DjangoPillowCheckpoint.to_dict, DjangoPillowCheckpoint.from_dict,
    )


def get_default_django_checkpoint_for_legacy_pillow_class(pillow_class):
    return PillowCheckpoint(get_django_checkpoint_store(), pillow_class.get_legacy_name())
