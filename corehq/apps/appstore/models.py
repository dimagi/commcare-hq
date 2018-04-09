from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit import ResourceNotFound
from corehq.apps.appstore.exceptions import CopiedFromDeletedException
from dimagi.ext.couchdbkit import *
from memoized import memoized


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
            try:
                doc = self.get(doc_id)
                return doc
            except ResourceNotFound:
                raise CopiedFromDeletedException(
                    'This snapshot points to a source domain that cannot be found. '
                    'The missing doc ID is: {}'.format(doc_id)
                )
        return None

    def get_updated_history(self):
        return self.copy_history + [self._id]
