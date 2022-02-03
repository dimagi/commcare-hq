from xml.etree import cElementTree as ElementTree

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from .utils import CASEBLOCK_CHUNKSIZE, submit_case_blocks


class CaseBulkDB:

    def __init__(self, domain, user_id, device_id):
        self.domain = domain
        self.user_id = user_id
        self.device_id = device_id

    def __enter__(self):
        self.to_save = []
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()

    def save(self, case_block):
        self.to_save.append(case_block)
        if len(self.to_save) >= CASEBLOCK_CHUNKSIZE:
            self.commit()

    def commit(self):
        if self.to_save:
            case_blocks = [
                ElementTree.tostring(case_block.as_xml(), encoding='utf-8').decode('utf-8')
                for case_block in self.to_save
            ]
            submit_case_blocks(case_blocks, self.domain, device_id=self.device_id, user_id=self.user_id)
            self.to_save = []


def update_cases(domain, update_fn, case_ids, user_id, device_id):
    """
    Perform a large number of case updates in chunks

    update_fn should be a function which accepts a case and returns a CaseBlock
    if an update is to be performed, or None to skip the case.
    """
    accessor = CaseAccessors(domain)
    with CaseBulkDB(domain, user_id, device_id) as bulk_db:
        for case in accessor.iter_cases(case_ids):
            case_block = update_fn(case)
            if case_block:
                bulk_db.save(case_block)
