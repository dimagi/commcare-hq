from datetime import date
from xml.etree import cElementTree as ElementTree

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import (
    get_last_non_blank_value,
    submit_case_blocks,
)
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
SEX_PROPERTY = "sex"
SEX_PROPERTY_MALE_VALUE = "M"
FEMALE_DEATH_TYPE_PROPERTY = "female_death_type"
HAS_DIED_PROPERTY = "died"
HAS_DIED_PROPERTY_YES_VALUE = "yes"


class DataManagementDocProcessor(BaseDocProcessor):
    def __init__(self, domain):
        self.domain = domain

    @staticmethod
    def _create_case_blocks(updates):
        case_blocks = []
        for case_id, case_updates in updates.items():
            case_block = CaseBlock.deprecated_init(case_id,
                                   update=case_updates,
                                   user_id=SYSTEM_USER_ID)
            case_block = ElementTree.tostring(case_block.as_xml()).decode('utf-8')
            case_blocks.append(case_block)
        return case_blocks

    def handle_skip(self, doc):
        print('Unable to process case {}'.format(doc['_id']))
        return True


class PopulateMissingMotherNameDocProcessor(DataManagementDocProcessor):
    def __init__(self, domain):
        super().__init__(domain)
        date_today = date.today()
        self.cut_off_dob = str(date_today.replace(year=date_today.year - CUT_OFF_AGE_IN_YEARS))
        self.test_location_ids = find_test_awc_location_ids(self.domain)
        self.case_accessor = CaseAccessors(self.domain)

    def process_bulk_docs(self, docs, progress_logger):
        updates = {}
        cases_updated = {}
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
                    updates[case_id] = {MOTHER_NAME_PROPERTY: mother_case.name}
                    cases_updated[case_id] = doc
        if updates:
            for case_id, case_doc in cases_updated.items():
                progress_logger.document_processed(case_doc, updates[case_id])
            submit_case_blocks(self._create_case_blocks(updates),
                               self.domain, user_id=SYSTEM_USER_ID)
        return True

    def should_process(self, doc):
        owner_id = doc.get('owner_id')
        if owner_id and owner_id in self.test_location_ids:
            return False
        dob = doc.get(DOB_PROPERTY)
        if dob and dob >= self.cut_off_dob and not doc.get(MOTHER_NAME_PROPERTY):
            return True
        return False


class SanitizePhoneNumberDocProcessor(DataManagementDocProcessor):
    def __init__(self, domain):
        super().__init__(domain)
        self.test_location_ids = find_test_awc_location_ids(self.domain)

    def process_bulk_docs(self, docs, progress_logger):
        if docs:
            updates = {doc['_id']: {PHONE_NUMBER_PROPERTY: ''} for doc in docs}
            for doc in docs:
                progress_logger.document_processed(doc, updates[doc['_id']])
            submit_case_blocks(self._create_case_blocks(updates),
                               self.domain, user_id=SYSTEM_USER_ID)
        return True

    def should_process(self, doc):
        owner_id = doc.get('owner_id')
        if owner_id and owner_id in self.test_location_ids:
            return False
        if doc.get(HAS_MOBILE_PROPERTY) == HAS_MOBILE_PROPERTY_NO_VALUE:
            return doc.get(PHONE_NUMBER_PROPERTY) == '91'
        return False


class SanitizeFemaleDeathTypeDocProcessor(DataManagementDocProcessor):
    """Sanitize: Reset female_death_type attribute to "" (empty):
       If the person record is MALE.
       (OR)
       If `died` attribute is not `yes`.

    Args:
        domain: Domain reference
    """
    def __init__(self, domain):
        super().__init__(domain)
        self.test_location_ids = find_test_awc_location_ids(self.domain)

    def process_bulk_docs(self, docs, progress_logger):
        if docs:
            updates = {doc['_id']: {FEMALE_DEATH_TYPE_PROPERTY: ''} for doc in docs}
            for doc in docs:
                progress_logger.document_processed(doc, updates[doc['_id']])
            submit_case_blocks(self._create_case_blocks(updates),
                               self.domain, user_id=SYSTEM_USER_ID)
        return True

    def should_process(self, doc):
        owner_id = doc.get('owner_id')
        if owner_id and owner_id in self.test_location_ids:
            return False
        if doc.get(SEX_PROPERTY) == SEX_PROPERTY_MALE_VALUE:
            return bool(doc.get(FEMALE_DEATH_TYPE_PROPERTY))
        if doc.get(HAS_DIED_PROPERTY) != HAS_DIED_PROPERTY_YES_VALUE:
            return bool(doc.get(FEMALE_DEATH_TYPE_PROPERTY))
        return False


class ResetMissingCaseNameDocProcessor(DataManagementDocProcessor):
    def __init__(self, domain):
        super().__init__(domain)
        self.case_accessor = CaseAccessors(self.domain)

    def process_bulk_docs(self, cases, progress_logger):
        updates = {}
        cases_updated = {}
        for case in cases:
            if self.should_process(case):
                update_to_name = get_last_non_blank_value(case, 'name')
                updates[case.case_id] = {'name': update_to_name}
                cases_updated[case.case_id] = case
        if updates:
            for case_id, case in cases_updated.items():
                progress_logger.document_processed(case, updates[case_id])
            submit_case_blocks(self._create_case_blocks(updates), self.domain, user_id=SYSTEM_USER_ID)
        return True

    def should_process(self, case):
        return not bool(case.name)
