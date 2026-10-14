from unittest.mock import Mock, patch

from django.core.cache import cache

import pytest
from celery.exceptions import Retry
from psycopg2 import errorcodes
from sqlalchemy.exc import OperationalError
from unmagic import fixture

from corehq.apps.project_db.tasks import (
    _sync_queued_key,
    schedule_project_db_sync,
    update_project_db_schema,
)

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
