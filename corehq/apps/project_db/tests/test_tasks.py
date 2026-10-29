import datetime
from contextlib import nullcontext
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

import pytest
import sqlalchemy
from celery.exceptions import Retry
from psycopg2 import errorcodes
from sqlalchemy.exc import OperationalError
from unmagic import fixture, use

from corehq.apps.project_db.models import PendingOperation
from corehq.apps.project_db.table_ddl import CaseTable, get_project_db_engine
from corehq.apps.project_db.tasks import (
    _process_pending_operations,
    _processing_queued_key,
    queue_stale_pending_operations,
    schedule_project_db_sync,
)

from .util import project_db_table

DOMAIN = 'project-db-signals-test'
SYNC_PATH = 'corehq.apps.project_db.tasks.create_or_update_project_db'
QUEUE_PATH = 'corehq.apps.project_db.tasks._queue_processing'


@fixture(autouse=__file__)
def clear_queued_flag():
    cache.delete(_processing_queued_key(DOMAIN))
    yield
    cache.delete(_processing_queued_key(DOMAIN))


@fixture
def queued():
    cache.set(_processing_queued_key(DOMAIN), True)
    yield


def _lock_timeout():
    return OperationalError('ALTER TABLE', {}, Mock(pgcode=errorcodes.LOCK_NOT_AVAILABLE))


def _record_sync(domain=DOMAIN):
    PendingOperation.objects.create(domain=domain, operation=PendingOperation.Operation.SYNC)


def _record_backfill(case_type, columns, domain=DOMAIN):
    PendingOperation.objects.create(
        domain=domain,
        operation=PendingOperation.Operation.BACKFILL,
        args={'case_type': case_type, 'columns': columns},
    )


def _pending_sync_count():
    return PendingOperation.objects.filter(
        domain=DOMAIN, operation=PendingOperation.Operation.SYNC).count()


@use('db')
def test_schedule_project_db_sync():
    with patch.object(_process_pending_operations, 'apply_async') as apply_mock:
        # Manages transaction.on_commit calls
        with TestCase.captureOnCommitCallbacks(execute=True):
            schedule_project_db_sync(DOMAIN)
            schedule_project_db_sync(DOMAIN)
            assert apply_mock.call_count == 0
    assert _pending_sync_count() == 2
    apply_mock.assert_called_once_with([DOMAIN], countdown=15)


@use('db')
def test_process_skips_sync_when_none_pending():
    with patch(SYNC_PATH) as sync_mock:
        _process_pending_operations(DOMAIN)
    sync_mock.assert_not_called()


@use('db', queued)
def test_process_retries_on_lock_timeout():
    _record_sync()
    err = _lock_timeout()
    with patch(SYNC_PATH, side_effect=err), \
         patch.object(_process_pending_operations, 'retry', side_effect=Retry) as retry_mock, \
         pytest.raises(Retry):
        _process_pending_operations(DOMAIN)
    retry_mock.assert_called_once_with(exc=err)
    assert _pending_sync_count() == 1
    assert cache.get(_processing_queued_key(DOMAIN))


@pytest.mark.parametrize('error', [
    None,
    ValueError(),
    _lock_timeout(),  # Called directly, retry() re-raises, as when retries are exhausted
])
@use('db', queued)
def test_process_clears_queued_flag(error):
    _record_sync()
    with patch(SYNC_PATH, side_effect=error), \
         pytest.raises(type(error)) if error else nullcontext():
        _process_pending_operations(DOMAIN)
    assert not cache.get(_processing_queued_key(DOMAIN))


@pytest.mark.parametrize('records_new_op', [True, False])
@use('db')
def test_process_requeues_operations_recorded_during_run(records_new_op):
    _record_sync()
    with patch(SYNC_PATH, lambda domain: _record_sync() if records_new_op else None), \
         patch(QUEUE_PATH) as queue_mock:
        _process_pending_operations(DOMAIN)
    assert queue_mock.called == records_new_op


@use('db', project_db_table('test-backfill-task', 'patient', {'dob': 'date'}, (
    ['case_id', 'owner_id', 'prop__dob'], [('a', 'o', '2020-01-01')],
)))
def test_process_applies_and_clears_pending_backfills():
    domain = 'test-backfill-task'
    _record_backfill('patient', ['date_prop__dob', 'date_prop__deleted'], domain)
    _record_backfill('patient', ['date_prop__dob'], domain)  # Duplicate
    _record_backfill('deleted', ['date_prop__dob'], domain)

    _process_pending_operations(domain)

    table = CaseTable(domain, 'patient').reflect()
    with get_project_db_engine().begin() as conn:
        dob = conn.execute(sqlalchemy.select([table.c.date_prop__dob])).scalar()
    assert dob == datetime.date(2020, 1, 1)
    assert not PendingOperation.objects.filter(domain=domain).exists()


@use('db')
def test_sweep_queues_domains_with_stale_operations():
    _record_sync(domain='stale-domain')
    PendingOperation.objects.update(created_on=timezone.now() - datetime.timedelta(hours=2))
    _record_sync(domain='fresh-domain')
    with patch(QUEUE_PATH) as queue_mock:
        queue_stale_pending_operations()
    queue_mock.assert_called_once_with('stale-domain')
