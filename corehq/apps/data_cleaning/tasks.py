from corehq.apps.celery import task

from casexml.apps.case.mock import CaseBlock
from corehq.apps.data_cleaning.models import (
    BulkEditSession,
)
from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE, submit_case_blocks
from corehq.apps.users.util import username_to_user_id
from corehq.form_processor.models import CommCareCase


@task(queue='case_import_queue')
def commit_data_cleaning(bulk_edit_session_id):
    session = BulkEditSession.objects.get(session_id=bulk_edit_session_id)

    form_ids = []
    case_index = 0
    while case_index < session.records.count():
        records = session.records.all()[case_index:case_index + CASEBLOCK_CHUNKSIZE]
        case_index += CASEBLOCK_CHUNKSIZE
        blocks = _create_case_blocks(session, records)
        form_ids.append(_submit_case_blocks(session, blocks))

    return form_ids


def _create_case_blocks(session, records):
    blocks = []
    case_ids = [rec.doc_id for rec in records]
    cases = {c.case_id: c for c in CommCareCase.objects.get_cases(case_ids, session.domain)}
    for record in records:
        for change in record.changes.all():
            case = cases[record.doc_id]
            blocks.append(CaseBlock(
                create=False,
                case_id=record.doc_id,
                update={change.prop_id: change.edited_value(case)},
            ))
    return blocks


def _submit_case_blocks(session, blocks):
    return submit_case_blocks(
        [block.as_text() for block in blocks],
        session.domain,
        session.user.username,
        username_to_user_id(session.user.username),
        device_id=__name__ + ".data_cleaning",
    )
