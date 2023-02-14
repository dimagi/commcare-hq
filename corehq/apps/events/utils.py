import uuid
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseBlock


def create_case_with_case_type(case_type, case_args):
    case_block = CaseBlock(
        case_id=uuid.uuid4().hex,
        case_type=case_type,
        case_name=case_args['name'],
        domain=case_args['domain'],
        owner_id=case_args['owner_id'],
        update=case_args['properties'],
        create=True,
    )
    form, cases = submit_case_blocks(
        [case_block.as_text()],
        domain=case_args['domain'],
    )
    return cases[0]
