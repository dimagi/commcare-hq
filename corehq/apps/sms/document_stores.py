from corehq.apps.sms.models import SMS
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import ReadOnlyDocumentStore


class ReadonlySMSDocumentStore(ReadOnlyDocumentStore):

    def get_document(self, doc_id):
        try:
            sms = SMS.objects.get(couch_id=doc_id)
        except SMS.DoesNotExist as e:
            raise DocumentNotFoundError(e)

        return sms.to_json()
