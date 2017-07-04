from __future__ import absolute_import

import hashlib
import logging
import os
import shutil
import tempfile
from io import FileIO
from cStringIO import StringIO
from uuid import uuid4
from celery.exceptions import TimeoutError
from celery.result import AsyncResult

from couchdbkit import ResourceNotFound
from casexml.apps.phone.data_providers import get_element_providers, get_full_response_providers
from casexml.apps.phone.exceptions import (
    MissingSyncLog, InvalidSyncLogException, SyncLogUserMismatch,
    BadStateException, RestoreException, DateOpenedBugException,
)
from casexml.apps.phone.tasks import get_async_restore_payload, ASYNC_RESTORE_SENT
from corehq.toggles import EXTENSION_CASES_SYNC_ENABLED, LIVEQUERY_SYNC
from corehq.util.timer import TimingContext
from corehq.util.datadog.gauges import datadog_counter
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.phone.models import (
    SyncLog,
    get_properly_wrapped_sync_log,
    OTARestoreUser,
    SimplifiedSyncLog,
)
from dimagi.utils.couch.database import get_db
from casexml.apps.phone import xml as xml_util
from datetime import datetime, timedelta
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from couchforms.openrosa_response import (
    ResponseNature,
    get_simple_response_xml,
    get_response_element,
)
from casexml.apps.case.xml import check_version, V1
from django.http import HttpResponse, StreamingHttpResponse
from django.conf import settings
from casexml.apps.phone.checksum import CaseStateHash
from casexml.apps.phone.const import (
    INITIAL_SYNC_CACHE_TIMEOUT,
    INITIAL_SYNC_CACHE_THRESHOLD,
    INITIAL_ASYNC_TIMEOUT_THRESHOLD,
    ASYNC_RETRY_AFTER,
    ASYNC_RESTORE_CACHE_KEY_PREFIX,
    RESTORE_CACHE_KEY_PREFIX,
)
from casexml.apps.phone.xml import get_sync_element, get_progress_element
from casexml.apps.phone.utils import get_restore_response_class
from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound

from wsgiref.util import FileWrapper
from xml.etree import ElementTree


logger = logging.getLogger(__name__)

# case sync algorithms
CLEAN_OWNERS = 'clean_owners'
LIVEQUERY = 'livequery'
DEFAULT_CASE_SYNC = CLEAN_OWNERS


def restore_cache_key(domain, prefix, user_id, version=None, sync_log_id=None, device_id=None):
    response_class = get_restore_response_class(domain)
    hashable_key = '{response_class}-{prefix}-{user}-{version}-{sync_log_id}-{device_id}'.format(
        response_class=response_class.__name__,
        prefix=prefix,
        user=user_id,
        version=version or '',
        sync_log_id=sync_log_id or '',
        device_id=device_id or '',
    )
    return hashlib.md5(hashable_key).hexdigest()


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


class RestoreResponse(object):
    start_tag_template = (
        '<OpenRosaResponse xmlns="http://openrosa.org/http/response"{items}>'
        '<message nature="{nature}">Successfully restored account {username}!</message>'
    )
    items_template = ' items="{}"'
    closing_tag = '</OpenRosaResponse>'

    def __init__(self, username=None, items=False):
        self.username = username
        self.items = items
        self.num_items = 0
        self.finalized = False

    def close(self):
        self.response_body.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def append(self, xml_element):
        self.num_items += 1
        if isinstance(xml_element, basestring):
            self.response_body.write(xml_element)
        else:
            self.response_body.write(xml_util.tostring(xml_element))

    def extend(self, iterable):
        for element in iterable:
            self.append(element)

    def finalize(self):
        raise NotImplemented()

    def as_string(self):
        raise NotImplemented()

    @classmethod
    def get_payload(cls, filename):
        '''
        Given a filename (or identifier) returns the associated payload as
        a filelike object. If it doesn't exist, return None.

        :filename: Identifier to lookup payload
        :returns: Filelike object or None
        '''
        raise NotImplemented()

    def __str__(self):
        return self.as_string()


class FileRestoreResponse(RestoreResponse):

    BODY_TAG_SUFFIX = '-body'
    EXTENSION = 'xml'

    def __init__(self, username=None, items=False):
        super(FileRestoreResponse, self).__init__(username, items)
        self.filename = os.path.join(settings.SHARED_DRIVE_CONF.restore_dir, uuid4().hex)

        self.response_body = FileIO(self.get_filename(self.BODY_TAG_SUFFIX), 'w+')

    def get_filename(self, suffix=None):
        return "{filename}{suffix}.{ext}".format(
            filename=self.filename,
            suffix=suffix or '',
            ext=self.EXTENSION
        )

    def __add__(self, other):
        if not isinstance(other, FileRestoreResponse):
            raise NotImplemented()

        response = FileRestoreResponse(self.username, self.items)
        response.num_items = self.num_items + other.num_items

        self.response_body.seek(0)
        other.response_body.seek(0)

        shutil.copyfileobj(self.response_body, response.response_body)
        shutil.copyfileobj(other.response_body, response.response_body)

        return response

    def finalize(self):
        """
        Creates the final file with start and ending tag
        """
        with open(self.get_filename(), 'w') as response:
            # Add 1 to num_items to account for message element
            items = self.items_template.format(self.num_items + 1) if self.items else ''
            response.write(self.start_tag_template.format(
                items=items,
                username=self.username,
                nature=ResponseNature.OTA_RESTORE_SUCCESS
            ))

            self.response_body.seek(0)
            shutil.copyfileobj(self.response_body, response)

            response.write(self.closing_tag)

        self.finalized = True
        self.close()

    def as_file(self):
        return open(self.get_filename(), 'r')

    @classmethod
    def get_payload(cls, filename):
        if os.path.exists(filename):
            return open(filename, 'r')
        return None

    @classmethod
    def get_content_length(cls, filename):
        return os.path.getsize(filename)

    def as_string(self):
        with open(self.get_filename(), 'r') as f:
            return f.read()

    def get_http_response(self):
        headers = {'Content-Length': os.path.getsize(self.get_filename())}
        return stream_response(open(self.get_filename(), 'r'), headers)


class BlobRestoreResponse(RestoreResponse):

    EXTENSION = 'xml'

    def __init__(self, username=None, items=False):
        super(BlobRestoreResponse, self).__init__(username, items)
        self.identifier = 'restore-response-{}'.format(uuid4().hex)

        self.response_body = tempfile.TemporaryFile('w+')

    def get_filename(self, suffix=None):
        return "{identifier}{suffix}.{ext}".format(
            identifier=self.identifier,
            suffix=suffix or '',
            ext=self.EXTENSION
        )

    def __add__(self, other):
        if not isinstance(other, BlobRestoreResponse):
            raise NotImplementedError

        response = BlobRestoreResponse(self.username, self.items)
        response.num_items = self.num_items + other.num_items

        self.response_body.seek(0)
        other.response_body.seek(0)

        shutil.copyfileobj(self.response_body, response.response_body)
        shutil.copyfileobj(other.response_body, response.response_body)

        return response

    def finalize(self):
        """
        Creates the final file with start and ending tag
        """
        with tempfile.TemporaryFile('w+') as response:
            # Add 1 to num_items to account for message element
            items = self.items_template.format(self.num_items + 1) if self.items else ''
            response.write(self.start_tag_template.format(
                items=items,
                username=self.username,
                nature=ResponseNature.OTA_RESTORE_SUCCESS
            ))

            self.response_body.seek(0)
            shutil.copyfileobj(self.response_body, response)

            response.write(self.closing_tag)
            response.seek(0)
            get_blob_db().put(response, self.get_filename(), timeout=60)

        self.finalized = True
        self.close()

    def as_file(self):
        return get_blob_db().get(self.get_filename())

    @classmethod
    def get_payload(cls, identifier):
        try:
            return get_blob_db().get(identifier)
        except NotFound:
            return None

    @classmethod
    def get_content_length(cls, identifier):
        return get_blob_db().size(identifier)

    def as_string(self):
        try:
            blob = get_blob_db().get(self.get_filename())
            return blob.read()
        finally:
            blob.close()

    def get_http_response(self):
        headers = {'Content-Length': get_blob_db().size(self.get_filename())}
        return stream_response(get_blob_db().get(self.get_filename()), headers)


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
            StringIO(self.compile_response()),
            status=202,
            headers=headers,
        )
        return response


class CachedResponse(object):

    def __init__(self, domain, payload_path):
        self.payload_path = payload_path
        self.restore_class = get_restore_response_class(domain)
        self.payload = self.restore_class.get_payload(self.payload_path) if payload_path else None

    def __nonzero__(self):
        return bool(self.payload)

    def as_string(self):
        try:
            return self.payload.read()
        finally:
            self.payload.close()

    def get_content_length(self):
        return self.restore_class.get_content_length(self.payload_path)

    def as_file(self):
        return self.payload

    def get_http_response(self):
        headers = {}
        content_length = self.get_content_length()
        if content_length is not None:
            headers['Content-Length'] = content_length
        return stream_response(self.payload, headers)


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
            app=None):
        self.sync_log_id = sync_log_id
        self.version = version
        self.state_hash = state_hash
        self.include_item_count = include_item_count
        self.app = app
        self.device_id = device_id

    @property
    def app_id(self):
        return self.app._id if self.app else None


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


class RestoreState(object):
    """
    The RestoreState object can be passed around to multiple restore data providers.

    This allows the providers to set values on the state, for either logging or performance
    reasons.
    """

    @property
    def restore_class(self):
        return get_restore_response_class(self.domain)

    def __init__(self, project, restore_user, params, async=False,
                 overwrite_cache=False, case_sync=None):
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
        self.async = async
        self.overwrite_cache = overwrite_cache
        self._last_sync_log = Ellipsis

        if case_sync is None:
            if LIVEQUERY_SYNC.enabled(self.domain):
                case_sync = LIVEQUERY
            else:
                case_sync = DEFAULT_CASE_SYNC
        if case_sync not in [LIVEQUERY, CLEAN_OWNERS]:
            raise ValueError("unknown case sync algorithm: %s" % case_sync)
        self.is_livequery = case_sync == LIVEQUERY

    def validate_state(self):
        check_version(self.params.version)
        if self.last_sync_log:
            if self.params.state_hash:
                parsed_hash = CaseStateHash.parse(self.params.state_hash)
                computed_hash = self.last_sync_log.get_state_hash()
                if computed_hash != parsed_hash:
                    # log state error on the sync log
                    self.last_sync_log.had_state_error = True
                    self.last_sync_log.error_date = datetime.utcnow()
                    self.last_sync_log.error_hash = str(parsed_hash)
                    self.last_sync_log.save()

                    raise BadStateException(
                        server_hash=computed_hash,
                        phone_hash=parsed_hash,
                        case_ids=self.last_sync_log.get_footprint_of_cases_on_phone()
                    )

    @property
    def last_sync_log(self):
        if self._last_sync_log is Ellipsis:
            if self.params.sync_log_id:
                try:
                    sync_log = get_properly_wrapped_sync_log(self.params.sync_log_id)
                    if settings.SERVER_ENVIRONMENT == "production":
                        self._check_for_date_opened_bug(sync_log)
                except ResourceNotFound:
                    # if we are in loose mode, return an HTTP 412 so that the phone will
                    # just force a fresh sync
                    raise MissingSyncLog('No sync log with ID {} found'.format(self.params.sync_log_id))
                if sync_log.doc_type != 'SyncLog':
                    raise InvalidSyncLogException('Bad sync log doc type for {}'.format(self.params.sync_log_id))
                elif sync_log.user_id != self.restore_user.user_id:
                    raise SyncLogUserMismatch('Sync log {} does not match user id {} (was {})'.format(
                        self.params.sync_log_id, self.restore_user.user_id, sync_log.user_id
                    ))

                # convert to the right type if necessary
                if not isinstance(sync_log, SimplifiedSyncLog):
                    # this call can fail with an IncompatibleSyncLogType error
                    sync_log = SimplifiedSyncLog.from_other_format(sync_log)
                self._last_sync_log = sync_log
            else:
                self._last_sync_log = None
        return self._last_sync_log

    def _check_for_date_opened_bug(self, sync_log):
        introduced_date = datetime(2016, 7, 19, 19, 15)
        reverted_date = datetime(2016, 7, 20, 9, 15)  # date bug was reverted on HQ
        resolved_date = datetime(2016, 7, 21, 0, 0)  # approximate date this fix was deployed

        if introduced_date < sync_log.date < reverted_date:
            raise DateOpenedBugException(self.restore_user, sync_log._id)

        # if the last synclog was before the time we pushed out this resolution,
        # we also need to check that they don't have a bad sync
        if reverted_date <= sync_log.date < resolved_date:
            synclogs = SyncLog.view(
                "phone/sync_logs_by_user",
                reduce=True,
                startkey=[sync_log.user_id, json_format_datetime(introduced_date), None],
                endkey=[sync_log.user_id, json_format_datetime(reverted_date), {}],
            ).first()
            if synclogs and synclogs.get('value') != 0:
                raise DateOpenedBugException(self.restore_user, sync_log._id)

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
        previous_log_rev = None if self.is_initial else self.last_sync_log._rev
        last_seq = str(get_db().info()["update_seq"])
        new_synclog = SimplifiedSyncLog(
            _id=SyncLog.get_db().server.next_uuid(),
            domain=self.restore_user.domain,
            build_id=self.params.app_id,
            user_id=self.restore_user.user_id,
            last_seq=last_seq,
            owner_ids_on_phone=set(self.owner_ids),
            date=datetime.utcnow(),
            previous_log_id=previous_log_id,
            previous_log_rev=previous_log_rev,
            extensions_checked=True,
        )
        return new_synclog

    @property
    @memoized
    def loadtest_factor(self):
        return self.restore_user.loadtest_factor


class RestoreConfig(object):
    """
    A collection of attributes associated with an OTA restore

    :param domain:          The domain object. An instance of `Domain`.
    :param restore_user:    The restore user requesting the restore
    :param params:          The RestoreParams associated with this (see above).
    :param cache_settings:  The RestoreCacheSettings associated with this (see above).
    :param async:           Whether to get the restore response using a celery task
    :param case_sync:       Case sync algorithm (None -> default).
    """

    def __init__(self, project=None, restore_user=None, params=None,
                 cache_settings=None, async=False, case_sync=None):
        assert isinstance(restore_user, OTARestoreUser)
        self.project = project
        self.domain = project.name if project else ''
        self.restore_user = restore_user
        self.params = params or RestoreParams()
        self.cache_settings = cache_settings or RestoreCacheSettings()
        self.async = async

        self.version = self.params.version
        self.restore_state = RestoreState(
            self.project,
            self.restore_user,
            self.params, async,
            self.cache_settings.overwrite_cache,
            case_sync=case_sync,
        )

        self.force_cache = self.cache_settings.force_cache or self.async
        self.cache_timeout = self.cache_settings.cache_timeout
        self.overwrite_cache = self.cache_settings.overwrite_cache

        self.timing_context = TimingContext('restore-{}-{}'.format(self.domain, self.restore_user.username))

    @property
    def cache(self):
        return get_redis_default_cache()

    @property
    @memoized
    def sync_log(self):
        return self.restore_state.last_sync_log

    @property
    def async_cache_key(self):
        return restore_cache_key(
            self.domain,
            ASYNC_RESTORE_CACHE_KEY_PREFIX,
            self.restore_user.user_id,
            sync_log_id=self.sync_log._id if self.sync_log else '',
            device_id=self.params.device_id,
        )

    @property
    def _restore_cache_key(self):
        return restore_cache_key(
            self.domain,
            RESTORE_CACHE_KEY_PREFIX,
            self.restore_user.user_id,
            version=self.version,
            sync_log_id=self.sync_log._id if self.sync_log else '',
            device_id=self.params.device_id,
        )

    def validate(self):
        try:
            self.restore_state.validate_state()
        except InvalidSyncLogException as e:
            # This exception will get caught by the view and a 412 will be returned to the phone for resync
            raise RestoreException(e)

    def get_payload(self):
        self.validate()
        self.delete_cached_payload_if_necessary()

        cached_response = self.get_cached_response()
        tags = [
            u'domain:{}'.format(self.domain),
            u'is_initial:{}'.format(not bool(self.sync_log)),
        ]
        if cached_response:
            datadog_counter('commcare.restores.cache_hits.count', tags=tags)
            return cached_response
        datadog_counter('commcare.restores.cache_misses.count', tags=tags)

        # Start new sync
        if self.async:
            response = self._get_asynchronous_payload()
        else:
            response = self.generate_payload()

        return response

    def generate_payload(self, async_task=None):
        self.restore_state.start_sync()
        response = self._generate_restore_response(async_task=async_task)
        self.restore_state.finish_sync()
        self.set_cached_payload_if_necessary(response, self.restore_state.duration)
        return response

    def get_cached_response(self):
        if self.overwrite_cache:
            return None

        cache_payload_path = self.cache.get(self._restore_cache_key)

        return CachedResponse(self.domain, cache_payload_path)

    def _get_asynchronous_payload(self):
        new_task = False
        # fetch the task from celery
        task_id = self.cache.get(self.async_cache_key)
        task = AsyncResult(task_id)
        task_exists = task.status == ASYNC_RESTORE_SENT

        if not task_exists:
            # start a new task
            task = get_async_restore_payload.delay(self)
            new_task = True
            # store the task id in cache
            self.cache.set(self.async_cache_key, task.id, timeout=24 * 60 * 60)
        try:
            response = task.get(timeout=self._get_task_timeout(new_task))
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
        This function returns a RestoreResponse class that encapsulates the response.
        """
        with self.restore_state.restore_class(
                self.restore_user.username, items=self.params.include_item_count) as response:
            element_providers = get_element_providers(self.timing_context)
            for provider in element_providers:
                with self.timing_context(provider.__class__.__name__):
                    for element in provider.get_elements(self.restore_state):
                        if element.tag == 'fixture' and len(element) == 0:
                            # There is a bug on mobile versions prior to 2.27 where
                            # a parsing error will cause mobile to ignore the element
                            # after this one if this element is empty.
                            # So we have to add a dummy empty_element child to prevent
                            # this element from being empty.
                            ElementTree.SubElement(element, 'empty_element')
                        response.append(element)

            full_response_providers = get_full_response_providers(self.timing_context, async_task)
            for provider in full_response_providers:
                with self.timing_context(provider.__class__.__name__):
                    partial_response = provider.get_response(self.restore_state)
                    response = response + partial_response
                    partial_response.close()

            response.finalize()
            return response

    def get_response(self):
        try:
            with self.timing_context:
                payload = self.get_payload()
            return payload.get_http_response()
        except RestoreException as e:
            logging.exception("%s error during restore submitted by %s: %s" %
                              (type(e).__name__, self.restore_user.username, str(e)))
            response = get_simple_response_xml(
                e.message,
                ResponseNature.OTA_RESTORE_ERROR
            )
            return HttpResponse(response, content_type="text/xml; charset=utf-8",
                                status=412)  # precondition failed

    def set_cached_payload_if_necessary(self, resp, duration):
        cache_payload_path = resp.get_filename()
        # on initial sync, only cache if the duration was longer than the threshold
        is_long_restore = duration > timedelta(seconds=INITIAL_SYNC_CACHE_THRESHOLD)

        if self.force_cache or is_long_restore or self.sync_log:
            self._set_cache_in_redis(cache_payload_path)

    def _set_cache_in_redis(self, cache_payload_path):
        self.cache.set(self._restore_cache_key, cache_payload_path, self.cache_timeout)

    def delete_cached_payload_if_necessary(self):
        if self.overwrite_cache and self.cache.get(self._restore_cache_key):
            self.cache.delete(self._restore_cache_key)
