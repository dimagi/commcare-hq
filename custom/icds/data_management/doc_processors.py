from datetime import date
from xml.etree import cElementTree as ElementTree

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.doc_processor.interface import BaseDocProcessor
from custom.icds.utils.location import find_test_awc_location_ids

DOB_PROPERTY = "dob"
MOTHER_NAME_PROPERTY = "mother_name"
CUT_OFF_AGE_IN_YEARS = 6
MOTHER_INDEX_IDENTIFIER = "mother"
PHONE_NUMBER_PROPERTY = "contact_phone_number"
HAS_MOBILE_PROPERTY = "has_mobile"
HAS_MOBILE_PROPERTY_NO_VALUE = "no"


class PopulateMissingMotherNameDocProcessor(BaseDocProcessor):
    def __init__(self, domain):
        self.domain = domain
        date_today = date.today()
        self.cut_off_dob = str(date_today.replace(year=date_today.year - CUT_OFF_AGE_IN_YEARS))
        self.test_location_ids = find_test_awc_location_ids(self.domain)
        self.case_accessor = CaseAccessors(self.domain)

    @staticmethod
    def _create_case_blocks(updates):
        case_blocks = []
        for case_id, mother_name in updates.items():
            case_block = CaseBlock(case_id,
                                   update={MOTHER_NAME_PROPERTY: mother_name},
                                   user_id=SYSTEM_USER_ID)
            case_block = ElementTree.tostring(case_block.as_xml()).decode('utf-8')
            case_blocks.append(case_block)
        return case_blocks

    def process_bulk_docs(self, docs):
        updates = {}
        for doc in docs:
            case_id = doc['_id']
            mother_case_ids = [i.referenced_id for i in CaseAccessorSQL.get_indices(self.domain, case_id)
                               if i.identifier == MOTHER_INDEX_IDENTIFIER]
            if len(mother_case_ids) == 1:
                try:
                    mother_case = self.case_accessor.get_case(mother_case_ids[0])
                except CaseNotFound:
                    pass
                else:
                    updates[case_id] = mother_case.name
        if updates:
            submit_case_blocks(self._create_case_blocks(updates), self.domain, user_id=SYSTEM_USER_ID)
        return True

    def handle_skip(self, doc):
        print('Unable to process case {}'.format(doc['_id']))
        return True

    def should_process(self, doc):
        owner_id = doc.get('owner_id')
        if owner_id and owner_id in self.test_location_ids:
            return False
        dob = doc.get(DOB_PROPERTY)
        if dob and dob >= self.cut_off_dob and not doc.get(MOTHER_NAME_PROPERTY):
            return True
        return False


class SanitizePhoneNumberDocProcessor(BaseDocProcessor):
    def __init__(self, domain):
        self.domain = domain
        self.test_location_ids = find_test_awc_location_ids(self.domain)

    @staticmethod
    def _create_case_blocks(docs):
        case_blocks = []
        for doc in docs:
            case_id = doc['_id']
            case_block = CaseBlock(case_id,
                                   update={PHONE_NUMBER_PROPERTY: ''},
                                   user_id=SYSTEM_USER_ID)
            case_block = ElementTree.tostring(case_block.as_xml()).decode('utf-8')
            case_blocks.append(case_block)
        return case_blocks

    def process_bulk_docs(self, docs):
        if docs:
            submit_case_blocks(self._create_case_blocks(docs), self.domain, user_id=SYSTEM_USER_ID)
        return True

    def handle_skip(self, doc):
        print('Unable to process case {}'.format(doc['_id']))
        return True

    def should_process(self, doc):
        owner_id = doc.get('owner_id')
        if owner_id and owner_id in self.test_location_ids:
            return False
        if doc.get(HAS_MOBILE_PROPERTY) == HAS_MOBILE_PROPERTY_NO_VALUE:
            return doc.get(PHONE_NUMBER_PROPERTY) == '91'
        return False
