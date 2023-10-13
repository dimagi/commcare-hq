import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from looseversion import LooseVersion
from io import BytesIO
from typing import Optional
from uuid import uuid4
from wsgiref.util import FileWrapper
from xml.etree import cElementTree as ElementTree

from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.text import slugify

from celery.exceptions import TimeoutError
from celery.result import AsyncResult
from memoized import memoized

from casexml.apps.case.xml import V1, check_version
from couchforms.openrosa_response import (
    ResponseNature,
    get_response_element,
    get_simple_response_xml,
)

from corehq.apps.domain.models import Domain
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.const import LOADTEST_HARD_LIMIT
from corehq.toggles import EXTENSION_CASES_SYNC_ENABLED
from corehq.util.metrics import metrics_counter, metrics_histogram
from corehq.util.timer import TimingContext
from dimagi.utils.logging import notify_error

from .checksum import CaseStateHash
from .const import (
    ASYNC_RETRY_AFTER,
    INITIAL_ASYNC_TIMEOUT_THRESHOLD,
    INITIAL_SYNC_CACHE_THRESHOLD,
    INITIAL_SYNC_CACHE_TIMEOUT,
)
from .data_providers import get_async_providers, get_element_providers
from .exceptions import (
    BadStateException,
    InvalidSyncLogException,
    RestoreException,
    SyncLogUserMismatch,
)
from .models import (
    LOG_FORMAT_LIVEQUERY,
    OTARestoreUser,
    SimplifiedSyncLog,
    get_properly_wrapped_sync_log,
)
from .restore_caching import AsyncRestoreTaskIdCache, RestorePayloadPathCache
from .tasks import ASYNC_RESTORE_SENT, get_async_restore_payload
from .utils import get_cached_items_with_count
from .xml import get_progress_element, get_sync_element

logger = logging.getLogger('restore')


def stream_response(payload, headers=None, status=200):
    try:
        response = StreamingHttpResponse(
            FileWrapper(payload),
            content_type="text/xml; charset=utf-8",
            status=status
        )
        if headers:
            for header, value in headers.items():
                response[header] = value
        return response
    except IOError as e:
        return HttpResponse(e, status=500)


class StockSettings(object):

    def __init__(self, section_to_consumption_types=None, consumption_config=None,
                 default_product_list=None, force_consumption_case_filter=None,
                 sync_consumption_ledger=False):
        """
        section_to_consumption_types should be a dict of stock section-ids to corresponding
        consumption section-ids. any stock sections not found in the dict will not have
        any consumption data set in the restore.

        force_consumption_case_filter allows you to force sending consumption data even if
        empty for a given CaseStub (id + type)
        """
        self.section_to_consumption_types = section_to_consumption_types or {}
        self.consumption_config = consumption_config
        self.default_product_list = default_product_list or []
        self.force_consumption_case_filter = force_consumption_case_filter or (lambda stub: False)
        self.sync_consumption_ledger = sync_consumption_ledger


class RestoreContent(object):
    start_tag_template = (
        b'<OpenRosaResponse xmlns="http://openrosa.org/http/response"%(items)s>'
        b'<message nature="%(nature)s">Successfully restored account %(username)s!</message>'
    )
    items_template = b' items="%s"'
    closing_tag = b'</OpenRosaResponse>'

    def __init__(self, username=None, items=False):
        self.username = username
        self.items = items
        self.num_items = 0

    def __enter__(self):
        self.response_body = tempfile.TemporaryFile('w+b')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.response_body.close()

    def append(self, xml_element):
        self.num_items += 1
        if isinstance(xml_element, bytes):
            xml_element, num = get_cached_items_with_count(xml_element)
            self.num_items += num - 1
            self.response_body.write(xml_element)
        else:
            self.response_body.write(ElementTree.tostring(xml_element, encoding='utf-8'))

    def extend(self, iterable):
        for element in iterable:
            self.append(element)

    def _write_to_file(self, fileobj):
        # Add 1 to num_items to account for message element
        items = (self.items_template % ('%s' % (self.num_items + 1)).encode('utf-8')) if self.items else b''
        fileobj.write(self.start_tag_template % {
            b"items": items,
            b"username": self.username.encode("utf8"),
            b"nature": ResponseNature.OTA_RESTORE_SUCCESS.encode("utf8"),
        })

        self.response_body.seek(0)
        shutil.copyfileobj(self.response_body, fileobj)

        fileobj.write(self.closing_tag)

    def get_fileobj(self):
        fileobj = tempfile.TemporaryFile('w+b')
        try:
            self._write_to_file(fileobj)
            fileobj.seek(0)
            return fileobj
        except:  # noqa
            fileobj.close()
            raise


class RestoreResponse(object):

    def __init__(self, fileobj):
        self.fileobj = fileobj

    def as_file(self):
        return self.fileobj

    def as_string(self):
        """Get content as utf8-encoded bytes

        NOTE: This method is only used in tests.
        Cannot be called more than once, and `self.as_file()` will
        return a closed file after this is called.
        """
        with self.fileobj:
            return self.fileobj.read()

    def get_http_response(self):
        self.fileobj.seek(0, os.SEEK_END)
        headers = {'Content-Length': self.fileobj.tell()}
        self.fileobj.seek(0)
        return stream_response(self.fileobj, headers)


class AsyncRestoreResponse(object):

    def __init__(self, task, username):
        self.task = task
        self.username = username

        task_info = self.task.info if self.task.info and isinstance(self.task.info, dict) else {}
        self.progress = {
            'done': task_info.get('done', 0),
            'total': task_info.get('total', 0),
            'retry_after': task_info.get('retry-after', ASYNC_RETRY_AFTER),
        }

    def compile_response(self):
        root = get_response_element(
            message="Asynchronous restore under way for {}".format(self.username),
            nature=ResponseNature.OTA_RESTORE_PENDING
        )
        sync_tag = get_sync_element()
        sync_tag.append(get_progress_element(**self.progress))
        root.append(sync_tag)

        return ElementTree.tostring(root, encoding='utf-8')

    def get_http_response(self):
        headers = {"Retry-After": self.progress['retry_after']}
        response = stream_response(
            BytesIO(self.compile_response()),
            status=202,
            headers=headers,
        )
        return response


class CachedResponse(object):

    def __init__(self, name):
        if name and name.startswith("restore-response-"):
            # Name template was 'restore-response-{}.xml' before new
            # blob metadata API was implemented. This can be removed
            # when all old responses have expired.
            #
            # '_default' is the bucket name from the old blob db API.
            name = "_default/" + name
        self.name = name

    @classmethod
    def save_for_later(cls, fileobj, timeout, domain, restore_user_id):
        """Save restore response for later

        :param fileobj: A file-like object.
        :param timeout: Minimum content expiration in seconds.
        :returns: A new `CachedResponse` pointing to the saved content.
        """
        name = 'restore-{}.xml'.format(uuid4().hex)
        get_blob_db().put(
            NoClose(fileobj),
            domain=domain,
            parent_id=restore_user_id,
            type_code=CODES.restore,
            key=name,
            timeout=max(timeout // 60, 60),
        )
        return cls(name)

    def __bool__(self):
        try:
            return bool(self.as_file())
        except NotFound:
            return False

    __nonzero__ = __bool__

    def as_string(self):
        with self.as_file() as fileobj:
            return fileobj.read()

    def as_file(self):
        try:
            value = self._fileobj
        except AttributeError:
            value = get_blob_db().get(key=self.name, type_code=CODES.restore) if self.name else None
            self._fileobj = value
        return value

    def get_http_response(self):
        file = self.as_file()
        headers = {'Content-Length': file.content_length}
        return stream_response(file, headers)


class RestoreParams(object):
    """
    Lightweight class that just handles grouping the possible attributes of a restore together.

    This is just for user-defined settings that can be configured via the URL.

    :param sync_log_id:         ID of the previous restore
    :param version:             The version of the restore format
    :param state_hash:          The case state hash string to use to verify the state of the phone
    :param include_item_count:  Set to `True` to include the item count in the response
    :param device_id:           The Device id of the device restoring
    """

    def __init__(self,
            sync_log_id='',
            version=V1,
            state_hash='',
            include_item_count=False,
            device_id=None,
            app=None,
            openrosa_version=None,
            fail_hard=False):
        self.sync_log_id = sync_log_id
        self.version = version
        self.state_hash = state_hash
        self.include_item_count = include_item_count
        self.app = app
        self.device_id = device_id
        self.openrosa_version = (LooseVersion(openrosa_version)
            if isinstance(openrosa_version, str) else openrosa_version)
        self.fail_hard = fail_hard

    @property
    def app_id(self):
        return self.app.get_id if self.app else None

    @property
    def is_webapps(self):
        return self.device_id and self.device_id.startswith("WebAppsLogin")

    def __repr__(self):
        return "RestoreParams(sync_log_id='{}', version={}, app='{}', device_id='{}')".format(
            self.sync_log_id,
            self.version,
            self.app,
            self.device_id,
        )


class RestoreCacheSettings(object):
    """
    Settings related to restore caching. These only apply if doing an initial restore and
    are not used if `RestoreParams.sync_log_id` is set.

    :param force_cache:     Set to `True` to force the response to be cached.
    :param cache_timeout:   Override the default cache timeout of 1 hour.
    :param overwrite_cache: Ignore any previously cached value and re-generate the restore response.
    """

    def __init__(self, force_cache=False, cache_timeout=None, overwrite_cache=False):
        self.force_cache = force_cache
        self.cache_timeout = cache_timeout if cache_timeout is not None else INITIAL_SYNC_CACHE_TIMEOUT
        self.overwrite_cache = overwrite_cache

    def __repr__(self):
        return "RestoreCacheSettings(force_cache='{}', cache_timeout={}, overwrite_cache='{}'".format(
            self.force_cache,
            self.cache_timeout,
            self.overwrite_cache
        )


class RestoreState:
    """
    The RestoreState object can be passed around to multiple restore
    data providers.

    This allows the providers to set values on the state, for either
    logging or performance reasons.
    """

    def __init__(
            self,
            project: Domain,
            restore_user: OTARestoreUser,
            params: RestoreParams,
            is_async: bool = False,
            overwrite_cache: bool = False,
            auth_type: Optional[str] = None,
    ):
        if not project or not project.name:
            raise Exception('you are not allowed to make a RestoreState without a domain!')

        self.project = project
        self.domain = project.name

        self.restore_user = restore_user
        self.params = params
        self.provider_log = {}  # individual data providers can log stuff here
        # get set in the start_sync() function
        self.start_time = None
        self.duration = None
        self.current_sync_log = None
        self.is_async = is_async
        self.overwrite_cache = overwrite_cache
        self.auth_type = auth_type
        self._last_sync_log = Ellipsis

    def validate_state(self):
        check_version(self.params.version)
        if self.last_sync_log and self.params.state_hash:
            parsed_hash = CaseStateHash.parse(self.params.state_hash)
            computed_hash = self.last_sync_log.get_state_hash()
            if computed_hash != parsed_hash:
                # log state error on the sync log
                self.last_sync_log.had_state_error = True
                self.last_sync_log.error_date = datetime.utcnow()
                self.last_sync_log.error_hash = str(parsed_hash)
                self.last_sync_log.save()

                if self.params.is_webapps:
                    # ignore this from webapps for now and just report
                    notify_error("State hash mismatch from webapps", details={
                        'synclog_id': self.params.sync_log_id,
                        'device_id': self.params.device_id,
                        'app_id': self.params.app_id,
                        'user_id': self.restore_user.user_id,
                        'request_user_id': self.restore_user.request_user_id,
                        'domain': self.domain,
                    })
                else:
                    raise BadStateException(
                        server_hash=computed_hash,
                        phone_hash=parsed_hash,
                        case_ids=self.last_sync_log.get_footprint_of_cases_on_phone()
                    )

    @property
    def last_sync_log(self):
        if self._last_sync_log is Ellipsis:
            if self.params.sync_log_id:
                # if we are in loose mode, return an HTTP 412 so that the phone will
                # just force a fresh sync
                # This raises MissingSyncLog exception if synclog not found
                sync_log = get_properly_wrapped_sync_log(self.params.sync_log_id)
                if sync_log.doc_type != 'SimplifiedSyncLog':
                    raise InvalidSyncLogException('Bad sync log doc type for {}'.format(self.params.sync_log_id))
                elif sync_log.user_id != self.restore_user.user_id:
                    raise SyncLogUserMismatch('Sync log {} does not match user id {} (was {})'.format(
                        self.params.sync_log_id, self.restore_user.user_id, sync_log.user_id
                    ))
                self._last_sync_log = sync_log
            else:
                self._last_sync_log = None
        return self._last_sync_log

    @property
    def is_initial(self):
        return self.last_sync_log is None

    @property
    def version(self):
        return self.params.version

    @property
    @memoized
    def owner_ids(self):
        return set(self.restore_user.get_owner_ids())

    @property
    @memoized
    def stock_settings(self):
        if self.project and self.project.commtrack_settings:
            return self.project.commtrack_settings.get_ota_restore_settings()
        else:
            return StockSettings()

    @property
    def is_first_extension_sync(self):
        extension_toggle_enabled = EXTENSION_CASES_SYNC_ENABLED.enabled(self.domain)
        try:
            return extension_toggle_enabled and not self.last_sync_log.extensions_checked
        except AttributeError:
            return extension_toggle_enabled

    def start_sync(self):
        self.start_time = datetime.utcnow()
        self.current_sync_log = self._new_sync_log()

    def finish_sync(self):
        self.duration = datetime.utcnow() - self.start_time
        self.current_sync_log.duration = self.duration.seconds
        self.current_sync_log.save()

    def _new_sync_log(self):
        previous_log_id = None if self.is_initial else self.last_sync_log._id
        new_synclog = SimplifiedSyncLog(
            _id=uuid.uuid1().hex.lower(),
            domain=self.restore_user.domain,
            build_id=self.params.app_id,
            user_id=self.restore_user.user_id,
            owner_ids_on_phone=set(self.owner_ids),
            date=datetime.utcnow(),
            previous_log_id=previous_log_id,
            extensions_checked=True,
            device_id=self.params.device_id,
            request_user_id=self.restore_user.request_user_id,
            auth_type=self.auth_type
        )
        if self.params.app:
            new_synclog.app_id = self.params.app.copy_of or self.params.app_id
        new_synclog.log_format = LOG_FORMAT_LIVEQUERY
        return new_synclog

    @memoized
    def get_safe_loadtest_factor(self, total_cases: int) -> int:
        """
        Ensures ``RestoreUser.loadtest_factor`` cannot result in a
        payload that exceeds ``LOADTEST_HARD_LIMIT`` number of cases
        (unless the user really has that many cases).
        """
        unsafe = self.restore_user.loadtest_factor
        max_factor = max(1, LOADTEST_HARD_LIMIT // total_cases)
        return min(unsafe, max_factor)

    def __repr__(self):
        return "RestoreState(project='{}', domain={}, restore_user='{}', start_time='{}', duration='{}'".format(
            self.project,
            self.domain,
            self.restore_user,
            self.start_time,
            self.duration
        )


class RestoreConfig(object):
    """
    A collection of attributes associated with an OTA restore

    :param project:         The domain object. An instance of `Domain`.
    :param restore_user:    The restore user requesting the restore
    :param params:          The RestoreParams associated with this (see above).
    :param cache_settings:  The RestoreCacheSettings associated with this (see above).
    :param is_async:           Whether to get the restore response using a celery task
    :param skip_fixtures:   Whether to include fixtures in the restore payload
    """

    def __init__(self, project=None, restore_user=None, params=None,
                 cache_settings=None, is_async=False,
                 skip_fixtures=False, auth_type=None):
        assert isinstance(restore_user, OTARestoreUser)
        self.project = project
        self.domain = project.name if project else ''
        self.restore_user = restore_user
        self.params = params or RestoreParams()
        self.cache_settings = cache_settings or RestoreCacheSettings()
        self.is_async = is_async
        self.skip_fixtures = skip_fixtures

        self.restore_state = RestoreState(
            self.project,
            self.restore_user,
            self.params, is_async,
            self.cache_settings.overwrite_cache,
            auth_type=auth_type
        )

        self.force_cache = self.cache_settings.force_cache
        self.cache_timeout = self.cache_settings.cache_timeout
        self.overwrite_cache = self.cache_settings.overwrite_cache

        self.timing_context = TimingContext('restore-{}-{}'.format(self.domain, self.restore_user.username))

    @property
    @memoized
    def sync_log(self):
        return self.restore_state.last_sync_log

    @property
    def async_restore_task_id_cache(self):
        return AsyncRestoreTaskIdCache(
            domain=self.domain,
            user_id=self.restore_user.user_id,
            sync_log_id=self.sync_log._id if self.sync_log else '',
            device_id=self.params.device_id,
        )

    @property
    def restore_payload_path_cache(self):
        return RestorePayloadPathCache(
            domain=self.domain,
            user_id=self.restore_user.user_id,
            sync_log_id=self.sync_log._id if self.sync_log else '',
            device_id=self.params.device_id,
        )

    @property
    def initial_restore_payload_path_cache(self):
        return RestorePayloadPathCache(
            domain=self.domain,
            user_id=self.restore_user.user_id,
            sync_log_id='',
            device_id=self.params.device_id,
        )

    def get_response(self):
        is_async = self.is_async
        try:
            with self.timing_context:
                payload = self.get_payload()
            response = payload.get_http_response()
        except RestoreException as e:
            logger.exception(
                "%s error during restore submitted by %s: %s" %
                (type(e).__name__, self.restore_user.username, str(e))
            )
            is_async = False
            response = get_simple_response_xml(
                str(e),
                ResponseNature.OTA_RESTORE_ERROR
            )
            response = HttpResponse(response, content_type="text/xml; charset=utf-8",
                                    status=412)  # precondition failed
        if not is_async:
            self._record_timing(response.status_code)
        return response

    def get_payload(self):
        self.validate()
        self.delete_initial_cached_payload_if_necessary()
        self.delete_cached_payload_if_necessary()

        cached_response = self.get_cached_response()
        tags = {
            'domain': self.domain,
            'is_async': bool(self.is_async),
        }
        if cached_response:
            metrics_counter('commcare.restores.cache_hits.count', tags=tags)
            return cached_response
        metrics_counter('commcare.restores.cache_misses.count', tags=tags)

        # Start new sync
        if self.is_async:
            response = self._get_asynchronous_payload()
        else:
            response = self.generate_payload()

        return response

    def validate(self):
        try:
            self.restore_state.validate_state()
        except InvalidSyncLogException as e:
            # This exception will get caught by the view and a 412 will be returned to the phone for resync
            raise RestoreException(e)

    def get_cached_response(self):
        if self.overwrite_cache:
            return None

        cache_payload_path = self.restore_payload_path_cache.get_value()

        return CachedResponse(cache_payload_path)

    def generate_payload(self, async_task=None):
        if async_task:
            self.timing_context.stop("wait_for_task_to_start")
        self.restore_state.start_sync()
        fileobj = self._generate_restore_response(async_task=async_task)
        try:
            self.restore_state.finish_sync()
            cached_response = self.set_cached_payload_if_necessary(
                fileobj, self.restore_state.duration, async_task)
            if async_task:
                fileobj.close()
                assert cached_response is not None
                response = cached_response
                self.timing_context.stop()  # root timer
                self._record_timing('async')
            else:
                fileobj.seek(0)
                response = RestoreResponse(fileobj)
        except:  # noqa
            fileobj.close()
            raise
        return response

    def _get_asynchronous_payload(self):
        new_task = False
        # fetch the task from celery
        task_id = self.async_restore_task_id_cache.get_value()
        if task_id:
            task = AsyncResult(task_id)
            task_exists = task.status == ASYNC_RESTORE_SENT
        else:
            task = None
            task_exists = False

        if not task_exists:
            # start a new task
            # NOTE this starts a nested timer (wait_for_task_to_start),
            # which will be stopped by self.generate_payload(async_task)
            # in the asynchronous task. It is expected that
            # get_async_restore_payload.delay(self) will serialize this
            # RestoreConfig and it's associated TimingContext before it
            # returns, and thereby fork the timing context. The timing
            # context associated with this side of the fork will not be
            # recorded since it is async (see self.get_response).
            with self.timing_context("wait_for_task_to_start"):
                task = get_async_restore_payload.delay(self, self.domain, self.restore_user.username)
                logger.info('RestoreConfig after get_async_restore_payload task is created: %r', self)
            new_task = True
            # store the task id in cache
            self.async_restore_task_id_cache.set_value(task.id)
        try:
            response_or_name = task.get(timeout=self._get_task_timeout(new_task))
            if isinstance(response_or_name, bytes):
                response_or_name = response_or_name.decode('utf-8')
            if isinstance(response_or_name, str):
                response = CachedResponse(response_or_name)
            else:
                response = response_or_name
        except TimeoutError:
            # return a 202 with progress
            response = AsyncRestoreResponse(task, self.restore_user.username)

        return response

    def _get_task_timeout(self, new_task):
        # if this is a new task, wait for INITIAL_ASYNC_TIMEOUT in case
        # this restore completes quickly. otherwise, only wait 1 second for
        # a response.
        return INITIAL_ASYNC_TIMEOUT_THRESHOLD if new_task else 1

    def _generate_restore_response(self, async_task=None):
        """
        :returns: A file-like object containing response content.
        """
        username = self.restore_user.username
        count_items = self.params.include_item_count
        with RestoreContent(username, count_items) as content:
            for provider in get_element_providers(self.timing_context, skip_fixtures=self.skip_fixtures):
                with self.timing_context(provider.__class__.__name__):
                    content.extend(provider.get_elements(self.restore_state))

            for provider in get_async_providers(self.timing_context, async_task):
                with self.timing_context(provider.__class__.__name__):
                    provider.extend_response(self.restore_state, content)

            return content.get_fileobj()

    def set_cached_payload_if_necessary(self, fileobj, duration, is_async):
        # must cache if the duration was longer than the threshold
        is_long_restore = duration > timedelta(seconds=INITIAL_SYNC_CACHE_THRESHOLD)
        if is_async or self.force_cache or is_long_restore:
            type_ = 'unknown'
            if is_async:
                type_ = 'async'
            elif self.force_cache:
                type_ = 'force'
            elif is_long_restore:
                type_ = 'long'

            tags = {
                'type': type_,
            }
            metrics_counter('commcare.restores.cache_writes', tags=tags)
            response = CachedResponse.save_for_later(
                fileobj,
                self.cache_timeout,
                self.domain,
                self.restore_user.user_id,
            )
            self.restore_payload_path_cache.set_value(response.name, self.cache_timeout)
            return response
        return None

    def delete_cached_payload_if_necessary(self):
        if self.overwrite_cache and self.restore_payload_path_cache.exists():
            self.restore_payload_path_cache.invalidate()

    def delete_initial_cached_payload_if_necessary(self):
        if self.sync_log:
            # Restores are usually cached by there sync token
            # but initial restores don't have a sync token,
            # so they're indistinguishable from each other.
            # Once a user syncs with a sync token, we're sure their initial sync is stale,
            # so delete it to avoid a stale payload if they (say) wipe the phone and sync again
            self.initial_restore_payload_path_cache.invalidate()

    def _record_timing(self, status):
        timing = self.timing_context
        assert timing.is_finished()
        duration = timing.duration
        if duration > 20 or status == 412:
            if status == 412:
                # use last sync log since there is no current sync log
                sync_log_id = self.params.sync_log_id or 'N/A'
            else:
                sync_log = self.restore_state.current_sync_log
                sync_log_id = sync_log._id if sync_log else 'N/A'
            logger.info(
                "restore %s: user=%s device=%s domain=%s status=%s duration=%.3f",
                sync_log_id,
                self.restore_user.username,
                self.params.device_id,
                self.domain,
                status,
                duration,
            )
        tags = {
            'status_code': status,
            'device_type': 'webapps' if self.params.is_webapps else 'other',
            'domain': self.domain,
        }
        timer_buckets = (1, 5, 20, 60, 120, 300, 600)
        for timer in timing.to_list(exclude_root=True):
            segment = None
            extra_tags = {}
            if timer.name in RESTORE_SEGMENTS:
                segment = RESTORE_SEGMENTS[timer.name]
            elif timer.name.startswith('fixture:'):
                segment = 'fixture'
                extra_tags = {'fixture': timer.name.split(':')[1]}

            if segment:
                metrics_histogram(
                    'commcare.restores.{}.duration.seconds'.format(segment), timer.duration,
                    bucket_tag='duration', buckets=timer_buckets, bucket_unit='s',
                    tags={**tags, **extra_tags}
                )
                metrics_counter(
                    'commcare.restores.{}'.format(segment),
                    tags={**tags, **extra_tags},
                )

        tags['type'] = 'sync' if self.params.sync_log_id else 'restore'

        if settings.ENTERPRISE_MODE:
            if self.params.app and self.params.app.copy_of:
                app_name = slugify(self.params.app.name)
                tags['app'] = '{}-{}'.format(app_name, self.params.app.version)
            else:
                tags['app'] = ''

        metrics_counter('commcare.restores.count', tags=tags)
        metrics_histogram(
            'commcare.restores.duration.seconds', timing.duration,
            bucket_tag='duration', buckets=timer_buckets, bucket_unit='s',
            tags=tags
        )

    def __repr__(self):
        return \
            "RestoreConfig(project='{}', domain={}, restore_user={}, cache_settings='{}', " \
            "is_async='{}', restore_state='{}', force_cache='{}', cache_timeout='{}', overwrite_cache='{}', " \
            "timing_context='{}')".format(
                self.project,
                self.domain,
                self.restore_user,
                self.cache_settings,
                self.is_async,
                self.restore_state,
                self.force_cache,
                self.cache_timeout,
                self.overwrite_cache,
                self.timing_context.to_dict()
            )


RESTORE_SEGMENTS = {
    "wait_for_task_to_start": "waiting",
    "FixtureElementProvider": "fixtures",
    "CasePayloadProvider": "cases",
}


class NoClose(object):
    """HACK file object with no-op `close()` to avoid close by S3Transfer

    https://github.com/boto/s3transfer/issues/80
    """

    def __init__(self, fileobj):
        self.fileobj = fileobj

    def __getattr__(self, name):
        return getattr(self.fileobj, name)

    def close(self):
        pass
