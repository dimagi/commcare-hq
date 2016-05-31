from casexml.apps.case.models import CommCareCase
from corehq.apps.sofabed.exceptions import InvalidDataException
from dimagi.utils.read_only import ReadOnlyObject
from pillowtop.listener import SQLPillow
from corehq.apps.sofabed.models import CaseData
import logging

logger = logging.getLogger('pillowtop')


class CaseDataPillow(SQLPillow):
    document_class = CommCareCase
    couch_filter = 'case/casedocs'
    include_docs = False

    def process_sql(self, doc_dict, delete=False):
        if delete or doc_dict['doc_type'] != 'CommCareCase':
            try:
                CaseData.objects.get(case_id=doc_dict['_id']).delete()
            except CaseData.DoesNotExist:
                pass
            return

        doc = self.document_class.wrap(doc_dict)
        doc = ReadOnlyObject(doc)
        try:
            CaseData.create_or_update_from_instance(doc)
        except InvalidDataException, e:
            # this is a less severe class of errors
            logger.info("CaseDataPillow: bad update in listener for line: %s\n%s" % (doc_dict, e))
