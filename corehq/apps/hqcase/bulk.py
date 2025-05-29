from dataclasses import dataclass

from corehq.apps.users.util import SYSTEM_USER_ID, username_to_user_id
from corehq.form_processor.models import CommCareCase

from .utils import submit_case_block_context


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


def update_cases(domain, update_fn, case_ids, form_meta: SystemFormMeta = None):
    """
    Perform a large number of case updates in chunks

    update_fn should be a function which accepts a case and returns a list of CaseBlock objects
    if an update is to be performed, or None to skip the case.

    Returns counts of number of updates made (not necessarily number of cases update).
    """
    form_meta = form_meta or SystemFormMeta()
    count = 0
    with submit_case_block_context(
        domain,
        device_id=form_meta.device_id,
        user_id=form_meta.user_id,
        username=form_meta.username,
    ) as submit_case_block:
        for case in CommCareCase.objects.iter_cases(case_ids):
            case_blocks = update_fn(case) or []
            for count, case_block in enumerate(case_blocks, start=1):
                submit_case_block.send(case_block)
    return count
