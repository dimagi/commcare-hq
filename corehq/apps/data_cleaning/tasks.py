from corehq.apps.celery import task

from casexml.apps.case.mock import CaseBlock
from corehq.apps.data_cleaning.models import (
    BulkEditSession,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.util import username_to_user_id
from corehq.form_processor.models import CommCareCase


@task(queue='case_import_queue')
def commit_data_cleaning(bulk_edit_session_id):
    session = BulkEditSession.objects.get(session_id=bulk_edit_session_id)

    caseblocks = []
    case_ids = set([rec.doc_id for rec in session.records.all()])
    cases = {c.case_id: c for c in CommCareCase.objects.get_cases(list(case_ids), session.domain)}
    for record in session.records.all():
        for change in record.changes.all():
            case = cases[record.doc_id]
            caseblocks.append(CaseBlock(
                create=False,
                case_id=record.doc_id,
                update={change.prop_id: change.edited_value(case)},
            ))

    return submit_case_blocks(
        [block.as_text() for block in caseblocks],
        session.domain,
        session.user.username,
        username_to_user_id(session.user.username),
        device_id=__name__ + ".data_cleaning",
    )
