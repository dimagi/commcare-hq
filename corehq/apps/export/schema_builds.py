"""
Deduplicated background builds of export schemas.

Generating an export schema can take several minutes, so it runs in
Celery (:func:`~corehq.apps.export.tasks.build_export_schema`). This
module gives each distinct build a :class:`SchemaBuildKey`, normally
allows only one unfinished build per key (concurrent requests join it;
see :func:`start_or_join_build` for the exception), tracks progress
through soil, and loads the finished schema.

Builds are identified to callers by a soil ``download_id``. A cache
entry maps the build key to that ID, and a :class:`BuildRecord` maps
the ID back to the key, so a status request can be validated against
the build it claims to belong to. They expire after
``BUILD_CACHE_TIMEOUT``.

State is kept in Django's default cache, which is also soil's default.
"""
import hashlib
import logging
import time
from dataclasses import astuple, dataclass, field

from couchdbkit.exceptions import ResourceNotFound
from django.core.cache import cache
from redis.exceptions import LockError

from soil import DownloadBase
from soil.progress import STATES, get_task_status

from dimagi.utils.couch import get_redis_lock

from corehq.apps.export.const import CASE_EXPORT
from corehq.apps.export.models import get_export_data_schema_class
from corehq.apps.export.tasks import build_export_schema
from corehq.util.metrics import metrics_counter

logger = logging.getLogger(__name__)

# How long build state is kept. Also the soil download's expiry.
BUILD_CACHE_TIMEOUT = 2 * 60 * 60
# An unfinished build older than this is presumed lost. It must be less
# than BUILD_CACHE_TIMEOUT, or the build's state expires first, and a
# lost build looks unknown instead of failed.
JOIN_MAX_AGE = 45 * 60
# How long a request waits for a build before showing the waiting page,
# so that small projects never see it.
HEAD_START_SECONDS = 1.5
POLL_INTERVAL = 0.25
# The lock is held only while checking for a build and queueing one.
LOCK_TIMEOUT = 10
LOCK_BLOCKING_TIMEOUT = 5
# Soil reports 100% as success. Progress is capped below that until the
# task has succeeded.
MAX_UNFINISHED_PERCENT = 99


@dataclass(frozen=True)
class SchemaBuildKey:
    export_type: str
    domain: str
    app_id: str | None
    identifier: str
    for_new_export_instance: bool

    def cache_key(self):
        digest = hashlib.sha1(repr(astuple(self)).encode('utf-8')).hexdigest()
        return f'export-schema-build:{digest}'


@dataclass(frozen=True)
class BuildRecord:
    cache_key: str
    domain: str
    started_at: float = field(default_factory=time.time)


def start_or_join_build(key):
    """Return the download_id of an unfinished build for ``key``,
    starting one if needed.

    If the lock cannot be acquired within a few seconds a build is
    started anyway: a duplicate build is better than a hung request.
    """
    lock = get_redis_lock(
        key.cache_key() + ':lock',
        timeout=LOCK_TIMEOUT,
        blocking_timeout=LOCK_BLOCKING_TIMEOUT,
        name='export_schema_build',
    )
    acquired = lock.acquire()
    if not acquired:
        logger.warning(
            'Timed out waiting for export schema build lock; starting a build '
            '(domain=%s, cache_key=%s)', key.domain, key.cache_key(),
        )
        metrics_counter('commcare.exports.schema_build.lock_timeout')
    try:
        download_id = cache.get(key.cache_key())
        if download_id and _is_joinable(download_id):
            metrics_counter('commcare.exports.schema_build', tags={'outcome': 'joined'})
            return download_id
        metrics_counter('commcare.exports.schema_build', tags={'outcome': 'started'})
        return _start_build(key)
    finally:
        if acquired:
            _release(lock)


def _release(lock):
    try:
        lock.release()
    except LockError:
        # The lock expired during a slow `delay()`; the build has started
        logger.warning(
            'Failed to release export schema build lock',
            exc_info=True,
        )


def _is_joinable(download_id):
    status = get_build_status(download_id)
    return status is not None and not _is_finished(status)


def _is_finished(status):
    return status.success() or status.failed()


def _start_build(key):
    download = DownloadBase()
    download.set_task(build_export_schema.delay(
        key.export_type,
        key.domain,
        key.app_id,
        key.identifier,
        key.for_new_export_instance,
    ))
    download.save(expiry=BUILD_CACHE_TIMEOUT)
    cache.set(key.cache_key(), download.download_id, BUILD_CACHE_TIMEOUT)
    record = BuildRecord(key.cache_key(), key.domain)
    cache.set(_record_key(download.download_id), record, BUILD_CACHE_TIMEOUT)
    return download.download_id


def _record_key(download_id):
    return f'export-schema-build-record:{download_id}'


def get_build_record(download_id):
    return cache.get(_record_key(download_id))


def get_build_status(download_id):
    """Return soil's ``TaskStatus`` for a build, or None if the build is
    unknown.

    Soil's status is corrected for a queued build (reported missing), a
    build at 100% that has not saved its schema yet (reported as
    succeeded), and a build that was lost (reported as running).
    """
    return _get_task_and_status(download_id)[1]


def _get_task_and_status(download_id):
    record = get_build_record(download_id)
    if record is None:
        return None, None
    download = DownloadBase.get(download_id)
    if download is None:
        return None, None
    task = download.task
    status = get_task_status(task)
    # The adjustments below are applied in order; each sees the last.
    if status.missing():
        # Soil reports a queued task as missing because the result
        # backend has no row for it yet. The build record proves that
        # the task exists.
        status = status._replace(state=STATES.not_started)
    if status.success() and not (task and task.successful()):
        # Soil reports success as soon as progress reaches 100%, but the
        # task gets there before it saves the schema.
        status = status._replace(state=STATES.started)
    age = time.time() - record.started_at
    if not status.success() and age > JOIN_MAX_AGE:
        # The task was probably lost with its worker. Report it as
        # failed so that the user can try again; the next request for
        # its key starts a new build.
        logger.warning(
            'Export schema build presumed lost (domain=%s, download_id=%s, state=%s, age=%ds)',
            record.domain, download_id, status.state, age,
        )
        status = status._replace(state=STATES.failed)
    if not status.success() and status.progress and status.progress.percent:
        percent = min(status.progress.percent, MAX_UNFINISHED_PERCENT)
        status = status._replace(progress=status.progress._replace(percent=percent))
    return task, status


def wait_for_build(download_id, timeout=HEAD_START_SECONDS):
    """Poll until the build finishes or ``timeout`` elapses. Return True
    if it succeeded.
    """
    deadline = time.monotonic() + timeout
    while True:
        status = get_build_status(download_id)
        if status is not None and _is_finished(status):
            return status.success()
        if time.monotonic() >= deadline:
            return False
        time.sleep(POLL_INTERVAL)


def get_built_schema(key, download_id):
    """Return the schema saved by a successful build for ``key``, or None.

    ``download_id`` can come from the query string, so the build and the
    schema it saved are both checked against ``key``.
    """
    record = get_build_record(download_id)
    if record is None or record.cache_key != key.cache_key():
        return None
    task, status = _get_task_and_status(download_id)
    if status is None or not status.success():
        return None
    schema_id = (task.result or {}).get('schema_id')
    if not schema_id:
        return None
    schema_cls = get_export_data_schema_class(key.export_type)
    try:
        schema = schema_cls.get(schema_id)
    except ResourceNotFound:
        return None
    return schema if _is_schema_for_key(schema, key) else None


def _is_schema_for_key(schema, key):
    identifier = schema.case_type if key.export_type == CASE_EXPORT else schema.xmlns
    return (
        schema.domain == key.domain
        and identifier == key.identifier
        # a missing app_id may be None or ''
        and (schema.app_id or None) == (key.app_id or None)
    )
