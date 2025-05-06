import logging
from corehq.apps.celery import task

from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count

from dimagi.utils.chunked import chunked

from casexml.apps.case.mock import CaseBlock
from corehq.apps.data_cleaning.utils.decorators import retry_on_integrity_error
from corehq.apps.data_cleaning.models import (
    BulkEditSession,
)
from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE, submit_case_blocks
from corehq.apps.receiverwrapper.rate_limiter import rate_limit_submission
from corehq.apps.users.util import username_to_user_id
from corehq.form_processor.models import CommCareCase
from corehq.util.metrics.load_counters import case_load_counter

logger = logging.getLogger(__name__)


@task(bind=True, queue='case_import_queue', acks_late=True)
def commit_data_cleaning(self, bulk_edit_session_id):
    updated = BulkEditSession.objects.filter(
        session_id=bulk_edit_session_id,
        completed_on__isnull=True,
    ).filter(
        Q(task_id__isnull=True)  # never claimed
        | Q(task_id=self.request.id)  # or already claimed by *this* worker
    ).update(
        task_id=self.request.id,
        committed_on=timezone.now(),
    )
    if not updated:
        logger.info("commit_data_cleaning: dropped task to avoid duplicaton", extra={
            'session_id': bulk_edit_session_id,
        })
        return []

    session = BulkEditSession.objects.get(session_id=bulk_edit_session_id)

    logger.info("commit_data_cleaning: starting", extra={
        'session_id': session.session_id,
        'domain': session.domain,
    })

    session.deselect_all_records_in_queryset()  # already in an atomic, retry block
    _purge_ui_data_from_session(session)

    form_ids = []
    session.update_result(0)
    count_cases = case_load_counter("bulk_case_cleaning", session.domain)
    errored_doc_ids = []

    record_iter = session.records.order_by('pk').iterator()
    for record_batch in chunked(record_iter, CASEBLOCK_CHUNKSIZE):
        blocks = _create_case_blocks(session, record_batch, errored_doc_ids)
        if not blocks:
            logger.info("commit_data_cleaning: no cases needed an update in a batch", extra={
                'session_id': session.session_id,
                'domain': session.domain,
                'record_batch': [record.doc_id for record in record_batch],
            })
            continue

        try:
            xform = _submit_case_blocks(session, blocks)
        except Exception as error:  # todo: catch specific errors seen with submitting case blocks
            doc_ids = [record.doc_id for record in record_batch]
            errored_doc_ids.extend(doc_ids)
            _record_submission_error(session, error, doc_ids)
            continue

        num_records = len(record_batch)
        count_cases(value=num_records * 2)  # 1 read + 1 write per case
        session.update_result(num_records, xform.form_id)
        form_ids.append(xform.form_id)

    _prune_records_and_complete_session(session, errored_doc_ids)
    logger.info("commit_data_cleaning: completed", extra={
        'session_id': session.session_id,
        'domain': session.domain,
    })

    return form_ids


@retry_on_integrity_error(max_retries=3, delay=0.1)
@transaction.atomic
def _purge_ui_data_from_session(session):
    session.filters.all().delete()
    session.pinned_filters.all().delete()
    session.columns.all().delete()
    session.purge_records()


@retry_on_integrity_error(max_retries=3, delay=0.1)
@transaction.atomic
def _prune_records_and_complete_session(session, errored_doc_ids):
    # remove errored records from session
    session.records.exclude(doc_id__in=errored_doc_ids).delete()
    # delete any change with zero remaining records
    session.changes.annotate(num_records=Count('records')).filter(num_records=0).delete()

    session.completed_on = timezone.now()
    session.save(update_fields=['completed_on'])


def _create_case_blocks(session, records, errored_doc_ids):
    blocks = []
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


def _record_submission_error(session, error, doc_ids):
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
