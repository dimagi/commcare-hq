from django.db import transaction
from corehq.apps.sofabed.exceptions import InvalidDataException
from dimagi.utils.read_only import ReadOnlyObject
from pillowtop.listener import BulkPillow
from couchforms.models import XFormInstance
from django.db.utils import DatabaseError
from corehq.apps.sofabed.models import FormData
import logging


class FormDataPillow(BulkPillow):
    document_class = XFormInstance
    couch_filter = 'couchforms/xforms'

    @transaction.commit_on_success
    def change_transport(self, doc_dict):
        doc = self.document_class.wrap(doc_dict)
        doc = ReadOnlyObject(doc)
        try:
            FormData.create_or_update_from_xforminstance(doc)
        except InvalidDataException, e:
            # this is a less severe class of errors
            logging.info("bad update in form listener for line: %s\n%s" % (doc_dict, e))

        except Exception, e:
            logging.exception("problem in form listener for line: %s\n%s" % (doc_dict, e))
            if isinstance(e, DatabaseError):
                # we have to do this manually to avoid issues with
                # open transactions
                transaction.rollback()

    def send_bulk(self, payload):
        pass