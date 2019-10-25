from corehq.apps.sms.models import SMS
from pillowtop.dao.django import DjangoDocumentStore


class ReadonlySMSDocumentStore(DjangoDocumentStore):
    def __init__(self):
        super().__init__(SMS, id_field='couch_id')
