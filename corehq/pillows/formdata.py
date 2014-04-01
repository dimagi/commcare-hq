from corehq.apps.sofabed.exceptions import InvalidDataException
from dimagi.utils.read_only import ReadOnlyObject
from pillowtop.listener import SQLPillow
from couchforms.models import XFormInstance
from corehq.apps.sofabed.models import FormData
import logging

logger = logging.getLogger('pillowtop')


class FormDataPillow(SQLPillow):
    document_class = XFormInstance
    couch_filter = 'couchforms/xforms'
    include_docs = False

    def process_sql(self, doc_dict):
        doc = self.document_class.wrap(doc_dict)
        doc = ReadOnlyObject(doc)

        try:
            FormData.create_or_update_from_xforminstance(doc)
        except InvalidDataException, e:
            # this is a less severe class of errors
            logger.info("FormDataPillow: bad update in form listener for line: %s\n%s" % (doc_dict, e))