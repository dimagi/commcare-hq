import datetime
import pytz
from pillowtop.dao.exceptions import DocumentNotFoundError


class PillowCheckpointManager(object):

    def __init__(self, dao):
        self._dao = dao

    def get_or_create_checkpoint(self, checkpoint_id):
        try:
            checkpoint_doc = self._dao.get_document(checkpoint_id)
        except DocumentNotFoundError:
            checkpoint_doc = {'seq': '0'}
            self._dao.save_document(checkpoint_id, checkpoint_doc)
        return checkpoint_doc

    def reset_checkpoint(self, checkpoint_id):
        checkpoint_doc = self.get_or_create_checkpoint(checkpoint_id)
        checkpoint_doc['old_seq'] = checkpoint_doc['seq']
        checkpoint_doc['seq'] = '0'
        checkpoint_doc['timestamp'] = datetime.now(tz=pytz.UTC).isoformat()
        self._dao.save_document(checkpoint_id, checkpoint_doc)
