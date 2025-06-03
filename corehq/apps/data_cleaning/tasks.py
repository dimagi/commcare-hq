import logging

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from corehq.apps.celery import task
from corehq.apps.data_cleaning.models import (
    BulkEditSession,
)
from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE, submit_case_blocks
from corehq.apps.receiverwrapper.rate_limiter import rate_limit_submission
from corehq.apps.users.util import username_to_user_id
from corehq.form_processor.models import CommCareCase
from corehq.util.metrics.load_counters import case_load_counter

logger = logging.getLogger(__name__)


@task(bind=True, queue='case_import_queue')
def commit_data_cleaning(self, bulk_edit_session_id):
    if not _claim_bulk_edit_session_for_task(self, bulk_edit_session_id):
        return []

    session = BulkEditSession.objects.get(session_id=bulk_edit_session_id)

    logger.info("commit_data_cleaning: starting", extra={
        'session_id': session.session_id,
        'domain': session.domain,
    })

    _purge_unedited_records(session)
    num_committed_records = session.records.count()

    form_ids = []
    session.update_result(0, num_committed_records=num_committed_records)
    count_cases = case_load_counter("bulk_case_cleaning", session.domain)

    record_iter = session.records.iterator()
    for record_batch in chunked(record_iter, CASEBLOCK_CHUNKSIZE):
        blocks, errored_doc_ids = _create_case_blocks(session, record_batch)
        if not blocks:
            _log_unusual_empty_case_block(session, record_batch)
            continue

        try:
            xform = _submit_case_blocks(session, blocks)
        except Exception as error:  # todo: catch specific errors seen with submitting case blocks
            _record_submission_error(session, error, record_batch)
            continue

        num_records = len(record_batch)
        count_cases(value=num_records * 2)  # 1 read + 1 write per case
        session.update_result(num_records, xform.form_id)
        form_ids.append(xform.form_id)
        _prune_completed_records(
            session,
            completed_doc_ids=[record.doc_id for record in record_batch],
            errored_doc_ids=errored_doc_ids,
        )

    session.completed_on = timezone.now()
    session.save(update_fields=['completed_on'])

    logger.info("commit_data_cleaning: completed", extra={
        'session_id': session.session_id,
        'domain': session.domain,
    })

    return form_ids


def _claim_bulk_edit_session_for_task(task, bulk_edit_session_id):
    updated = BulkEditSession.objects.filter(
        session_id=bulk_edit_session_id,
        completed_on__isnull=True,
    ).filter(
        Q(task_id__isnull=True)  # never claimed
        | Q(task_id=task.request.id)  # or already claimed by *this* worker
    ).update(
        task_id=task.request.id,
    )
    if not updated:
        logger.info("commit_data_cleaning: dropped task to avoid duplication", extra={
            'session_id': bulk_edit_session_id,
        })
        return False
    return True


@transaction.atomic
def _purge_unedited_records(session):
    session.deselect_all_records_in_queryset()
    session.purge_records()


@transaction.atomic
def _prune_completed_records(session, completed_doc_ids, errored_doc_ids):
    ids_to_delete = set(completed_doc_ids) - set(errored_doc_ids)
    session.records.filter(doc_id__in=ids_to_delete).delete()
    session.changes.filter(records__isnull=True).delete()


def _create_case_blocks(session, records):
    blocks = []
    errored_doc_ids = []
    case_ids = [rec.doc_id for rec in records]
    cases = {c.case_id: c for c in CommCareCase.objects.get_cases(case_ids, session.domain)}
    for record in records:
        case = cases[record.doc_id]
        try:
            update = record.get_edited_case_properties(case)
        except Exception as error:  # todo: catch specific errors seen with case interactions
            errored_doc_ids.append(record.doc_id)
            _record_case_block_creation_error(session, error, record.doc_id)
            continue
        if update:
            blocks.append(CaseBlock(
                create=False,
                case_id=record.doc_id,
                update=update,
            ))
    return blocks, errored_doc_ids


def _submit_case_blocks(session, blocks):
    rate_limit_submission(session.domain, delay_rather_than_reject=True)

    return submit_case_blocks(
        [block.as_text() for block in blocks],
        session.domain,
        session.user.username,
        username_to_user_id(session.user.username),
        device_id=__name__ + ".data_cleaning",
    )[0]


def _log_unusual_empty_case_block(session, record_batch):
    logger.info("commit_data_cleaning: no cases needed an update in a batch", extra={
        'session_id': session.session_id,
        'domain': session.domain,
        'record_batch': [record.doc_id for record in record_batch],
    })


def _record_case_block_creation_error(session, error, doc_id):
    session.update_result(0, error={
        'error': str(error),
        'doc_id': doc_id,
    })
    logger.error("commit_data_cleaning: error getting edited case properties", extra={
        'session_id': session.session_id,
        'domain': session.domain,
        'error': str(error),
        'doc_id': doc_id,
    })


def _record_submission_error(session, error, record_batch):
    doc_ids = [record.doc_id for record in record_batch]
    session.update_result(0, error={
        'error': str(error),
        'doc_ids': doc_ids,
    })
    logger.error("commit_data_cleaning: error submitting case blocks", extra={
        'session_id': session.session_id,
        'domain': session.domain,
        'error': str(error),
        'doc_ids': doc_ids,
    })
