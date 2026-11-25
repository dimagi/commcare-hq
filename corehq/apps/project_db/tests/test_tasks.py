import datetime
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
    _queue_processing,
    queue_stale_pending_operations,
    schedule_project_db_sync,
)

from .util import project_db_table

DOMAIN = 'project-db-signals-test'
CREATE_OR_UPDATE_PATH = 'corehq.apps.project_db.tasks.create_or_update_project_db'
SYNC_PATH = 'corehq.apps.project_db.tasks._apply_pending_sync'
QUEUE_PATH = 'corehq.apps.project_db.tasks._queue_processing'


@fixture(autouse=__file__)
def clear_queued_flag():
    yield
    cache.delete(_processing_queued_key(DOMAIN))


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
        # Executes transaction.on_commit calls on exit
        with TestCase.captureOnCommitCallbacks(execute=True):
            schedule_project_db_sync(DOMAIN)
            schedule_project_db_sync(DOMAIN)
            assert _pending_sync_count() == 2
            apply_mock.assert_not_called()
        apply_mock.assert_called_once_with([DOMAIN], countdown=15)


@use('db')
def test_process_skips_sync_when_none_pending():
    with patch(CREATE_OR_UPDATE_PATH) as sync_mock:
        _process_pending_operations(DOMAIN)
    sync_mock.assert_not_called()


@use('db')
def test_process_retries_on_lock_timeout():
    cache.set(_processing_queued_key(DOMAIN), True)

    # When _apply_pending_sync hits a write lock, retry
    write_lock_err = _lock_timeout()
    with (
        patch(SYNC_PATH, side_effect=write_lock_err),
        patch.object(_process_pending_operations, 'retry', side_effect=Retry) as retry_mock,
        pytest.raises(Retry),  # Swallows the above Retry exception
    ):
        _process_pending_operations(DOMAIN)
    retry_mock.assert_called_once_with(exc=write_lock_err)

    # If it's a retry, the key shouldn't be cleared
    assert cache.get(_processing_queued_key(DOMAIN))


@use('db')
def test_process_clears_queued_flag():
    cache.set(_processing_queued_key(DOMAIN), True)
    _process_pending_operations(DOMAIN)
    assert not cache.get(_processing_queued_key(DOMAIN))


@use('db')
def test_process_with_hard_failure_clears_queued_flag():
    cache.set(_processing_queued_key(DOMAIN), True)
    with patch(SYNC_PATH, side_effect=ValueError), pytest.raises(ValueError):
        _process_pending_operations(DOMAIN)
    assert not cache.get(_processing_queued_key(DOMAIN))


@use('db')
def test_process_requeues_operations_recorded_during_run():
    def record_sync_on_first_run(domain):
        if create_mock.call_count == 1:
            _record_sync()

    _record_sync()
    with patch(CREATE_OR_UPDATE_PATH, side_effect=record_sync_on_first_run) as create_mock:
        _queue_processing(DOMAIN)

    assert create_mock.call_count == 2
    assert _pending_sync_count() == 0
    assert not cache.get(_processing_queued_key(DOMAIN))


@use('db', project_db_table('test-backfill-task', 'patient', {'dob': 'date'}, (
    ['case_id', 'owner_id', 'prop__dob'], [('a', 'o', '2020-01-01')],
)))
def test_process_applies_and_clears_pending_backfills():
    domain = 'test-backfill-task'
    _record_backfill('patient', ['date_prop__dob', 'date_prop__missing'], domain)
    _record_backfill('patient', ['date_prop__dob'], domain)  # Duplicate
    _record_backfill('missing', ['date_prop__dob'], domain)

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
