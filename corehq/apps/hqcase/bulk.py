from dataclasses import dataclass
from xml.etree import cElementTree as ElementTree

from corehq.apps.users.util import SYSTEM_USER_ID, username_to_user_id
from corehq.form_processor.models import CommCareCase

from .utils import CASEBLOCK_CHUNKSIZE, submit_case_blocks


@dataclass(frozen=True)
class SystemFormMeta:
    user_id: str = SYSTEM_USER_ID
    username: str = SYSTEM_USER_ID
    device_id: str = SYSTEM_USER_ID

    @classmethod
    def for_script(cls, name, username=None):
        user_kwargs = {}
        if username:
            user_id = username_to_user_id(username)
            if not user_id:
                raise Exception(f"User '{username}' not found")
            user_kwargs = {
                'user_id': user_id,
                'username': username,
            }

        return cls(
            device_id=name,
            **user_kwargs,
        )


class CaseBulkDB:
    """
    Context manager to facilitate making case changes in chunks.
    """

    def __init__(self, domain, form_meta: SystemFormMeta = None):
        self.domain = domain
        self.form_meta = form_meta or SystemFormMeta()

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
            submit_case_blocks(
                case_blocks,
                self.domain,
                device_id=self.form_meta.device_id,
                user_id=self.form_meta.user_id,
                username=self.form_meta.username,
            )
            self.to_save = []


def update_cases(domain, update_fn, case_ids, form_meta: SystemFormMeta = None):
    """
    Perform a large number of case updates in chunks

    update_fn should be a function which accepts a case and returns a list of CaseBlock objects
    if an update is to be performed, or None to skip the case.

    Returns counts of number of updates made (not necessarily number of cases update).
    """
    update_count = 0
    with CaseBulkDB(domain, form_meta) as bulk_db:
        for case in CommCareCase.objects.iter_cases(case_ids):
            case_blocks = update_fn(case)
            if case_blocks:
                for case_block in case_blocks:
                    bulk_db.save(case_block)
                    update_count += 1
    return update_count
