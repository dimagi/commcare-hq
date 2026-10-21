import datetime
from unittest.mock import Mock, patch

from django.core.cache import cache

import pytest
from celery.exceptions import Retry
from psycopg2 import errorcodes
import sqlalchemy
from sqlalchemy.exc import OperationalError
from unmagic import fixture, use

from corehq.apps.project_db.table_ddl import CaseTable, get_project_db_engine
from corehq.apps.project_db.tasks import (
    _sync_queued_key,
    backfill_project_db_columns,
    schedule_project_db_sync,
    update_project_db_schema,
)

from .util import project_db_table

DOMAIN = 'project-db-signals-test'


@fixture(autouse=__file__)
def clear_sync_flag():
    cache.delete(_sync_queued_key(DOMAIN))
    yield
    cache.delete(_sync_queued_key(DOMAIN))


def test_schedule_one_at_a_time():
    with patch.object(update_project_db_schema, 'apply_async') as apply_mock:
        schedule_project_db_sync(DOMAIN)
        assert apply_mock.call_count == 1

        # Second call noops
        schedule_project_db_sync(DOMAIN)
        assert apply_mock.call_count == 1

        with patch('corehq.apps.project_db.tasks.create_or_update_project_db'):
            # This should clear the flag and allow another `apply` to go through
            update_project_db_schema(DOMAIN)

        schedule_project_db_sync(DOMAIN)
        assert apply_mock.call_count == 2


def test_eager_mode_syncs_every_time():
    with patch('corehq.apps.project_db.tasks.create_or_update_project_db') as sync_mock:
        schedule_project_db_sync(DOMAIN)
        schedule_project_db_sync(DOMAIN)
    assert sync_mock.call_count == 2


def test_sync_retries_on_lock_timeout():
    err = OperationalError('ALTER TABLE', {}, Mock(pgcode=errorcodes.LOCK_NOT_AVAILABLE))
    with patch('corehq.apps.project_db.tasks.create_or_update_project_db', side_effect=err), \
         patch.object(update_project_db_schema, 'retry', side_effect=Retry) as retry_mock, \
         pytest.raises(Retry):
        update_project_db_schema(DOMAIN)
    retry_mock.assert_called_once_with(exc=err)


def test_sync_queues_backfill():
    to_backfill = {'patient': ['date_prop__dob']}
    with patch('corehq.apps.project_db.tasks.create_or_update_project_db', return_value=to_backfill), \
         patch.object(backfill_project_db_columns, 'delay') as delay_mock:
        update_project_db_schema(DOMAIN)
    delay_mock.assert_called_once_with(DOMAIN, 'patient', ['date_prop__dob'])


@use('db', project_db_table('test-backfill-task', 'patient', {'dob': 'date'}, (
    ['case_id', 'owner_id', 'prop__dob'], [('a', 'o', '2020-01-01')],
)))
def test_backfill_project_db_columns():
    backfill_project_db_columns('test-backfill-task', 'patient', ['date_prop__dob'])

    table = CaseTable('test-backfill-task', 'patient').reflect()
    with get_project_db_engine().begin() as conn:
        dob = conn.execute(sqlalchemy.select([table.c.date_prop__dob])).scalar()
    assert dob == datetime.date(2020, 1, 1)
