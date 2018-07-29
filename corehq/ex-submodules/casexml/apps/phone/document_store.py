from __future__ import absolute_import
from casexml.apps.phone.models import SyncLogSQL
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import ReadOnlyDocumentStore


class ReadonlySyncLogDocumentStore(ReadOnlyDocumentStore):

    def get_document(self, doc_id):
        try:
            sycnlog = SyncLogSQL.objects.get(synclog_id=doc_id)
        except SyncLogSQL.DoesNotExist as e:
            raise DocumentNotFoundError(e)

        return sycnlog.doc
