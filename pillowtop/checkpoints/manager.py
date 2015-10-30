from datetime import datetime
from dateutil import parser
import pytz
from pillowtop.checkpoints.util import get_formatted_current_timestamp
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.exceptions import PillowtopCheckpointReset


class PillowCheckpointManager(object):

    def __init__(self, dao):
        self._dao = dao

    def get_or_create_checkpoint(self, checkpoint_id):
        try:
            checkpoint_doc = self._dao.get_document(checkpoint_id)
        except DocumentNotFoundError:
            checkpoint_doc = {'seq': '0', 'timestamp': get_formatted_current_timestamp()}
            self._dao.save_document(checkpoint_id, checkpoint_doc)
        return checkpoint_doc

    def reset_checkpoint(self, checkpoint_id):
        checkpoint_doc = self.get_or_create_checkpoint(checkpoint_id)
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
        checkpoint = self._manager.get_or_create_checkpoint(self.checkpoint_id)
        if verify_unchanged and self._last_checkpoint and checkpoint['seq'] != self._last_checkpoint['seq']:
            raise PillowtopCheckpointReset(u'Checkpoint {} expected seq {} but found {} in database.'.format(
                self.checkpoint_id, self._last_checkpoint['seq'], checkpoint['seq'],
            ))

        self._last_checkpoint = checkpoint
        return checkpoint

    def update_to(self, seq):
        checkpoint = self.get_or_create(verify_unchanged=True)
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
        checkpoint = self.get_or_create(verify_unchanged=True)
        now = datetime.now(tz=pytz.UTC)
        previous = self._last_checkpoint.get('timestamp')
        do_update = True
        if previous:
            diff = now - parser.parse(previous).replace(tzinfo=pytz.UTC)
            do_update = diff.total_seconds() >= min_interval
        if do_update:
            checkpoint['timestamp'] = now.isoformat()
            self._manager.update_checkpoint(self.checkpoint_id, checkpoint)
