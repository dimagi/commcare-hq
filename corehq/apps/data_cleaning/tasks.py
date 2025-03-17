from datetime import datetime
from corehq.apps.celery import task

from casexml.apps.case.mock import CaseBlock
from corehq.apps.data_cleaning.models import (
    BulkEditColumn,
    BulkEditColumnFilter,
    BulkEditPinnedFilter,
    BulkEditSession,
)
from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE, submit_case_blocks
from corehq.apps.receiverwrapper.rate_limiter import rate_limit_submission
from corehq.apps.users.util import username_to_user_id
from corehq.form_processor.models import CommCareCase
from corehq.util.metrics.load_counters import case_load_counter


@task(queue='case_import_queue')
def commit_data_cleaning(bulk_edit_session_id):
    session = BulkEditSession.objects.get(session_id=bulk_edit_session_id)

    # Delete UI-only models
    BulkEditColumnFilter.objects.filter(session=session).delete()
    BulkEditPinnedFilter.objects.filter(session=session).delete()
    BulkEditColumn.objects.filter(session=session).delete()

    form_ids = []
    case_index = 0
    session.update_result(0)
    count_cases = case_load_counter("bulk_case_cleaning", session.domain)
    while case_index < session.records.count():
        records = session.records.all()[case_index:case_index + CASEBLOCK_CHUNKSIZE]
        case_index += CASEBLOCK_CHUNKSIZE
        blocks = _create_case_blocks(session, records)
        xform = _submit_case_blocks(session, blocks)
        count_cases(value=len(records) * 2)       # 1 read + 1 write per case
        form_ids.append(xform.form_id)
        session.update_result(len(records), xform.form_id)
        session.save()

    session.completed_on = datetime.now()
    session.save()

    return form_ids


def _create_case_blocks(session, records):
    blocks = []
    case_ids = [rec.doc_id for rec in records]
    cases = {c.case_id: c for c in CommCareCase.objects.get_cases(case_ids, session.domain)}
    for record in records:
        case = cases[record.doc_id]
        update = record.get_edited_case_properties(case)
        if update:
            blocks.append(CaseBlock(
                create=False,
                case_id=record.doc_id,
                update=update,
            ))
    return blocks


def _submit_case_blocks(session, blocks):
    rate_limit_submission(session.domain, delay_rather_than_reject=True)

    return submit_case_blocks(
        [block.as_text() for block in blocks],
        session.domain,
        session.user.username,
        username_to_user_id(session.user.username),
        device_id=__name__ + ".data_cleaning",
    )[0]
