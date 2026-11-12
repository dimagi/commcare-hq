import time
from dataclasses import replace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from celery import Task
from couchdbkit.exceptions import ResourceNotFound
from django.core.cache import cache
from django.test import TestCase
from redis.exceptions import LockNotOwnedError
from soil.progress import STATES, TaskStatus
from unmagic import fixture, use

from corehq.apps.export import schema_builds
from corehq.apps.export.models import CaseExportDataSchema, FormExportDataSchema
from corehq.apps.export.schema_builds import (
    SchemaBuildKey,
    get_build_record,
    get_build_status,
    get_built_schema,
    start_or_join_build,
    wait_for_build,
)
from corehq.apps.export.tests.util import StoreEagerCeleryResults

KEY = SchemaBuildKey('form', 'test-domain', 'app123', 'xmlns', False)
CASE_KEY = SchemaBuildKey('case', 'test-domain', None, 'person', True)


def make_status(state):
    return TaskStatus(result=None, error=None, state=state, progress=None, exception=None)


class FakeBuilds:
    """Stands in for Celery and soil: ``delay`` hands out task ids, ``state`` is the status"""

    def __init__(self):
        self.state = STATES.started
        self.schema_id = 'schema-1'
        self.delay = Mock(side_effect=lambda *a: Mock(task_id=f'task-{self.delay.call_count}'))

    def get_task_status(self, task):
        return make_status(self.state)

    def get_task(self, download):
        """Stands in for the build's Celery ``AsyncResult``"""
        return Mock(
            successful=Mock(return_value=self.state == STATES.success),
            result={'schema_id': self.schema_id},
        )


@fixture
def builds():
    fake = FakeBuilds()
    cache.clear()
    with (
        patch.object(schema_builds.build_export_schema, 'delay', fake.delay),
        patch.object(schema_builds, 'get_task_status', fake.get_task_status),
        patch.object(schema_builds.DownloadBase, 'task', property(fake.get_task)),
    ):
        yield fake
    cache.clear()


@pytest.mark.parametrize('state', [STATES.started, STATES.not_started, STATES.missing])
@use(builds)
def test_unfinished_build_is_joined(state):
    builds().state = state
    first = start_or_join_build(KEY)
    second = start_or_join_build(KEY)
    assert first == second
    assert builds().delay.call_count == 1


@use(builds)
def test_queued_build_reported_missing_is_not_started():
    # Soil reports a queued task as missing: the result backend has no row yet
    builds().state = STATES.missing
    download_id = start_or_join_build(KEY)
    assert get_build_status(download_id).not_started()


@use(builds)
def test_task_is_started_with_key_fields():
    start_or_join_build(KEY)
    builds().delay.assert_called_once_with('form', 'test-domain', 'app123', 'xmlns', False)


@use(builds)
def test_different_keys_start_separate_builds():
    first = start_or_join_build(KEY)
    second = start_or_join_build(replace(KEY, for_new_export_instance=True))
    assert first != second
    assert builds().delay.call_count == 2


def succeed(download_id):
    builds().state = STATES.success


def fail(download_id):
    builds().state = STATES.failed


def expire(download_id):
    cache.delete(schema_builds._record_key(download_id))


def make_stale(download_id):
    record = get_build_record(download_id)
    started_at = time.time() - schema_builds.JOIN_MAX_AGE - 1
    cache.set(schema_builds._record_key(download_id), replace(record, started_at=started_at))


@pytest.mark.parametrize('end_build', [succeed, fail, expire, make_stale])
@use(builds)
def test_ended_build_is_not_joined(end_build):
    first = start_or_join_build(KEY)
    end_build(first)
    second = start_or_join_build(KEY)
    assert first != second
    assert builds().delay.call_count == 2


@pytest.mark.parametrize('state, expected', [
    (STATES.not_started, STATES.failed),
    (STATES.started, STATES.failed),
    (STATES.missing, STATES.failed),
    (STATES.success, STATES.success),
])
@use(builds)
def test_stale_build_status(state, expected):
    download_id = start_or_join_build(KEY)
    builds().state = state
    make_stale(download_id)
    with patch.object(schema_builds, 'logger') as logger:
        assert get_build_status(download_id).state == expected
    assert logger.warning.called == (expected == STATES.failed)


@use(builds)
def test_lock_timeout_starts_build_without_lock():
    lock = Mock()
    lock.acquire.return_value = False
    with (
        patch.object(schema_builds, 'get_redis_lock', return_value=lock) as get_lock,
        patch.object(schema_builds, 'logger') as logger,
        patch.object(schema_builds, 'metrics_counter') as counter,
    ):
        download_id = start_or_join_build(KEY)
    assert download_id
    assert builds().delay.call_count == 1
    assert get_lock.call_args.kwargs['blocking_timeout'] > 0
    lock.release.assert_not_called()
    logger.warning.assert_called_once()
    counter.assert_any_call('commcare.exports.schema_build.lock_timeout')


@use(builds)
def test_build_outcome_metrics():
    with patch.object(schema_builds, 'metrics_counter') as counter:
        start_or_join_build(KEY)
        start_or_join_build(KEY)
    assert [c.kwargs['tags']['outcome'] for c in counter.call_args_list] == ['started', 'joined']


@use(builds)
def test_lock_is_released():
    lock = Mock()
    lock.acquire.return_value = True
    with patch.object(schema_builds, 'get_redis_lock', return_value=lock):
        start_or_join_build(KEY)
    lock.release.assert_called_once_with()


@use(builds)
def test_lock_release_error_does_not_fail_started_build():
    lock = Mock()
    lock.acquire.return_value = True
    lock.release.side_effect = LockNotOwnedError('Cannot release a lock that is no longer owned')
    with (
        patch.object(schema_builds, 'get_redis_lock', return_value=lock),
        patch.object(schema_builds, 'logger') as logger,
    ):
        download_id = start_or_join_build(KEY)
    assert get_build_record(download_id).cache_key == KEY.cache_key()
    logger.warning.assert_called_once()


@use(builds)
def test_build_record_stores_cache_key_and_domain():
    download_id = start_or_join_build(KEY)
    record = get_build_record(download_id)
    assert record.cache_key == KEY.cache_key()
    assert record.domain == 'test-domain'
    assert time.time() - 5 < record.started_at <= time.time()


def test_cache_key_depends_on_every_field():
    keys = {
        KEY.cache_key(),
        replace(KEY, export_type='case').cache_key(),
        replace(KEY, domain='other').cache_key(),
        replace(KEY, app_id=None).cache_key(),
        replace(KEY, identifier='other').cache_key(),
        replace(KEY, for_new_export_instance=True).cache_key(),
    }
    assert len(keys) == 6
    assert all(k.startswith('export-schema-build:') for k in keys)


@use(builds)
def test_unknown_build():
    assert get_build_status('nope') is None
    assert get_built_schema(KEY, 'nope') is None
    assert wait_for_build('nope', timeout=0.3) is False


def get_built_schema_from(key, schema):
    download_id = start_or_join_build(key)
    builds().state = STATES.success
    with patch.object(type(schema), 'get', return_value=schema) as get:
        built = get_built_schema(key, download_id)
    return built, get


@pytest.mark.parametrize('key, schema', [
    (KEY, FormExportDataSchema(domain='test-domain', app_id='app123', xmlns='xmlns')),
    (CASE_KEY, CaseExportDataSchema(domain='test-domain', app_id=None, case_type='person')),
])
@use(builds)
def test_get_built_schema_loads_schema_from_task_result(key, schema):
    built, get = get_built_schema_from(key, schema)
    assert built is schema
    get.assert_called_once_with('schema-1')


@pytest.mark.parametrize('key, schema', [
    (KEY, FormExportDataSchema(domain='other-domain', app_id='app123', xmlns='xmlns')),
    (KEY, FormExportDataSchema(domain='test-domain', app_id='other-app', xmlns='xmlns')),
    (KEY, FormExportDataSchema(domain='test-domain', app_id='app123', xmlns='other-xmlns')),
    (CASE_KEY, CaseExportDataSchema(domain='test-domain', app_id=None, case_type='household')),
])
@use(builds)
def test_get_built_schema_rejects_schema_for_other_key(key, schema):
    built, get = get_built_schema_from(key, schema)
    assert built is None


@use(builds)
def test_get_built_schema_handles_missing_schema_doc():
    download_id = start_or_join_build(KEY)
    builds().state = STATES.success
    with patch.object(FormExportDataSchema, 'get', side_effect=ResourceNotFound):
        assert get_built_schema(KEY, download_id) is None


@use(builds)
def test_get_built_schema_rejects_build_for_other_key():
    download_id = start_or_join_build(KEY)
    builds().state = STATES.success
    assert get_built_schema(replace(KEY, identifier='other'), download_id) is None


@use(builds)
def test_get_built_schema_rejects_unfinished():
    download_id = start_or_join_build(KEY)
    assert get_built_schema(KEY, download_id) is None


@pytest.mark.parametrize('state, expected', [
    (STATES.started, False),
    (STATES.success, True),
    (STATES.failed, False),
])
@use(builds)
def test_wait_for_build(state, expected):
    download_id = start_or_join_build(KEY)
    builds().state = state
    assert wait_for_build(download_id, timeout=0.3) is expected


class TestBuildAtFullProgressBeforeTaskFinishes(StoreEagerCeleryResults, TestCase):
    """The task reports progress n of n before it merges and saves the schema

    Soil treats 100% progress as success, but the schema is not saved
    until the Celery task itself has succeeded.
    """

    def setUp(self):
        super().setUp()
        self.addCleanup(cache.clear)
        self.task = Task().AsyncResult(uuid4().hex)
        self.task.backend.store_result(self.task.id, {'current': 3, 'total': 3}, 'PROGRESS')
        with patch.object(schema_builds.build_export_schema, 'delay', return_value=self.task):
            self.download_id = start_or_join_build(KEY)

    def test_status_is_not_success(self):
        status = get_build_status(self.download_id)
        assert status.started()
        assert status.progress.percent == 99

    def test_build_is_joined(self):
        with patch.object(schema_builds.build_export_schema, 'delay') as delay:
            assert start_or_join_build(KEY) == self.download_id
        delay.assert_not_called()

    def test_schema_is_not_loaded(self):
        with patch.object(FormExportDataSchema, 'get') as get:
            assert get_built_schema(KEY, self.download_id) is None
        get.assert_not_called()

    def test_status_is_success_once_task_succeeds(self):
        self.task.backend.store_result(self.task.id, {'schema_id': 'schema-1'}, 'SUCCESS')
        assert get_build_status(self.download_id).success()
