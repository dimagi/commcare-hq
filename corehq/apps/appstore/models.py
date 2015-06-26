from dimagi.ext.couchdbkit import *
from dimagi.utils.decorators.memoized import memoized


class SnapshotMixin(DocumentSchema):
    copy_history = StringListProperty()

    @property
    def is_copy(self):
        return True if self.copy_history else False

    @property
    @memoized
    def copied_from(self):
        doc_id = self.copy_history[-1] if self.is_copy else None
        if doc_id:
            doc = self.get(doc_id)
            return doc
        return None

    def get_updated_history(self):
        return self.copy_history + [self._id]
