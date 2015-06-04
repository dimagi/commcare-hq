from StringIO import StringIO
from io import FileIO
from os import path
import os
from uuid import uuid4
import shutil
import hashlib
import tempfile
from celery.exceptions import TimeoutError
from couchdbkit import ResourceConflict, ResourceNotFound
from casexml.apps.phone.data_providers import get_restore_providers, get_long_running_providers
from casexml.apps.phone.data_providers.case.load_testing import get_loadtest_factor
from casexml.apps.phone.exceptions import (
    MissingSyncLog, InvalidSyncLogException, SyncLogUserMismatch,
    BadStateException, RestoreException,
)
from casexml.apps.phone.tasks import async_restore_response
from corehq.toggles import LOOSE_SYNC_TOKEN_VALIDATION, FILE_RESTORE
from corehq.util.soft_assert import soft_assert
from dimagi.utils.decorators.memoized import memoized
from casexml.apps.phone.models import SyncLog, get_properly_wrapped_sync_log
import logging
from dimagi.utils.couch.database import get_db, get_safe_write_kwargs
from casexml.apps.phone import xml
from datetime import datetime, timedelta
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from couchforms.xml import (
    ResponseNature,
    get_simple_response_xml,
)
from casexml.apps.case.xml import check_version, V1, V3
from django.http import HttpResponse, StreamingHttpResponse
from django.conf import settings
from casexml.apps.phone.checksum import CaseStateHash
from wsgiref.util import FileWrapper

logger = logging.getLogger(__name__)

# how long a cached payload sits around for (in seconds).
INITIAL_SYNC_CACHE_TIMEOUT = 60 * 60  # 1 hour

# the threshold for setting a cached payload on initial sync (in seconds).
# restores that take less than this time will not be cached to allow
# for rapid iteration on fixtures/cases/etc.
INITIAL_SYNC_CACHE_THRESHOLD = 60  # 1 minute


def stream_response(payload, is_file=True, status=None, headers=None):
    try:
        if is_file:
            response = StreamingHttpResponse(FileWrapper(open(payload, 'r')), status=status, mimetype="text/xml")
            response['Content-Length'] = os.path.getsize(payload)
            if headers:
                for name, value in headers.items():
                    response[name] = value
            return response
        else:
            return StreamingHttpResponse(FileWrapper(payload), mimetype="text/xml")
    except IOError as e:
        return HttpResponse(e, status=500)


class StockSettings(object):

    def __init__(self, section_to_consumption_types=None, consumption_config=None,
                 default_product_list=None, force_consumption_case_filter=None):
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


class RestoreResponse(object):
    start_tag_template = (
        '<OpenRosaResponse xmlns="http://openrosa.org/http/response"{items}>'
        '<message nature="{nature}">{message}</message>'
    )
    items_template = ' items="{}"'
    closing_tag = '</OpenRosaResponse>'
    full_response_message = 'Successfully restored account {username}!'
    partial_response_message = 'Partial response for account {username}. Retry again in 30 seconds.'

    def __init__(self, username=None, items=False):
        self.username = username
        self.items = items
        self.num_items = 0
        self.finalized = False
        self.is_full_restore = False

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
            self.response_body.write(xml.tostring(xml_element))

    def extend(self, iterable):
        for element in iterable:
            self.append(element)

    def finalize(self, is_full_restore):
        raise NotImplemented()

    def get_cache_payload(self, full=False):
        raise NotImplemented()

    def as_string(self):
        raise NotImplemented()

    def __str__(self):
        return self.as_string()


class FileRestoreResponse(RestoreResponse):

    BODY_TAG_SUFFIX = '-body'
    EXTENSION = 'xml'

    def __init__(self, username=None, items=False):
        super(FileRestoreResponse, self).__init__(username, items)
        self.filename = path.join(settings.SHARED_DRIVE_CONF.restore_dir, uuid4().hex)

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

    def finalize(self, is_full_restore):
        """
        Creates the final file with start and ending tag
        """
        with open(self.get_filename(), 'w') as response:
            # Add 1 to num_items to account for message element
            items = self.items_template.format(self.num_items + 1) if self.items else ''
            message = self.full_response_message if is_full_restore else self.partial_response_message
            response.write(self.start_tag_template.format(
                items=items,
                message=message.format(username=self.username),
                nature=ResponseNature.OTA_RESTORE_SUCCESS
            ))

            self.response_body.seek(0)
            shutil.copyfileobj(self.response_body, response)

            response.write(self.closing_tag)
        
        self.finalized = True
        self.is_full_restore = is_full_restore
        self.close()

    def get_cache_payload(self, full=False):
        return {
            'is_file': True,
            'data': self.get_filename() if not full else open(self.get_filename(), 'r')
        }

    def as_string(self):
        with open(self.get_filename(), 'r') as f:
            return f.read()

    def get_http_response(self):
        headers = {}
        status = None
        if not self.is_full_restore:
            headers['Retry-After'] = 30
            status = 202
        return stream_response(self.get_filename(), status=status, headers=headers)


class StringRestoreResponse(RestoreResponse):

    def __init__(self, username=None, items=False):
        super(StringRestoreResponse, self).__init__(username, items)
        self.response_body = StringIO()
        self.response = None

    def __add__(self, other):
        if not isinstance(other, StringRestoreResponse):
            raise NotImplemented()

        response = StringRestoreResponse(self.username, self.items)
        response.num_items = self.num_items + other.num_items
        response.response_body.write(self.response_body.getvalue())
        response.response_body.write(other.response_body.getvalue())

        return response

    def finalize(self):
        # Add 1 to num_items to account for message element
        items = self.items_template.format(self.num_items + 1) if self.items else ''
        self.response = '{start}{body}{end}'.format(
            start=self.start_tag_template.format(
                items=items,
                username=self.username,
                nature=ResponseNature.OTA_RESTORE_SUCCESS),
            body=self.response_body.getvalue(),
            end=self.closing_tag
        )
        self.finalized = True
        self.close()

    def get_cache_payload(self, full=False):
        return {
            'is_file': False,
            'data': self.response
        }

    def as_string(self):
        return self.response

    def get_http_response(self):
        return HttpResponse(self.response, mimetype="text/xml")


class CachedResponse(object):
    def __init__(self, payload):
        self.is_file = False
        self.is_stream = False
        self.payload = payload
        if isinstance(payload, dict):
            self.payload = payload['data']
            self.is_file = payload['is_file']
        elif hasattr(payload, 'read'):
            self.is_stream = True

    def exists(self):
        return self.payload and (not self.is_file or path.exists(self.payload))

    def as_string(self):
        if self.is_stream:
            return self.payload.read()
        if self.is_file:
            with open(self.payload, 'r') as f:
                return f.read()
        else:
            return self.payload

    def get_http_response(self):
        if self.is_stream:
            return stream_response(self.payload, is_file=False)
        if self.is_file:
            return stream_response(self.payload, is_file=True)
        else:
            return HttpResponse(self.payload, mimetype="text/xml")


def get_restore_class(domain, user):
    restore_class = StringRestoreResponse
    if FILE_RESTORE.enabled(domain) or FILE_RESTORE.enabled(user.username):
        restore_class = FileRestoreResponse

    return restore_class


class RestoreParams(object):
    """
    Lightweight class that just handles grouping the possible attributes of a restore together.

    This is just for user-defined settings that can be configured via the URL.

    :param sync_log_id:         ID of the previous restore
    :param version:             The version of the restore format
    :param state_hash:          The case state hash string to use to verify the state of the phone
    :param include_item_count:  Set to `True` to include the item count in the response
    """

    def __init__(self, sync_log_id='', version=V1, state_hash='', include_item_count=False):
        self.sync_log_id = sync_log_id
        self.version = version
        self.state_hash = state_hash
        self.include_item_count = include_item_count


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
    def __init__(self, project, user, params):
        self.project = project
        self.domain = project.name if project else ''
        _assert = soft_assert(to=['czue' + '@' + 'dimagi.com'], fail_if_debug=True)
        _assert(self.domain, 'Restore for {} missing a domain!'.format(user.username))

        self.user = user
        self.params = params
        self.provider_log = {}  # individual data providers can log stuff here
        # get set in the start_sync() function
        self.start_time = None
        self.duration = None
        self.current_sync_log = None

    def validate_state(self):
        check_version(self.params.version)
        if self.last_sync_log and self.params.state_hash:
            parsed_hash = CaseStateHash.parse(self.params.state_hash)
            computed_hash = self.last_sync_log.get_state_hash()
            if computed_hash != parsed_hash:
                raise BadStateException(expected=computed_hash,
                                        actual=parsed_hash,
                                        case_ids=self.last_sync_log.get_footprint_of_cases_on_phone())

    @property
    @memoized
    def last_sync_log(self):
        if self.params.sync_log_id:
            try:
                sync_log = get_properly_wrapped_sync_log(self.params.sync_log_id)
            except ResourceNotFound:
                # if we are in loose mode, return an HTTP 412 so that the phone will
                # just force a fresh sync
                raise MissingSyncLog('No sync log with ID {} found'.format(self.params.sync_log_id))
            if sync_log.doc_type != 'SyncLog':
                raise InvalidSyncLogException('Bad sync log doc type for {}'.format(self.params.sync_log_id))
            elif sync_log.user_id != self.user.user_id:
                raise SyncLogUserMismatch('Sync log {} does not match user id {} (was {})'.format(
                    self.params.sync_log_id, self.user.user_id, sync_log.user_id
                ))

            return sync_log
        else:
            return None

    @property
    def is_initial(self):
        return self.last_sync_log is None

    @property
    def version(self):
        return self.params.version

    @property
    @memoized
    def owner_ids(self):
        return set(self.user.get_owner_ids())

    @property
    @memoized
    def stock_settings(self):
        if self.project and self.project.commtrack_settings:
            return self.project.commtrack_settings.get_ota_restore_settings()
        else:
            return StockSettings()

    def start_sync(self):
        self.start_time = datetime.utcnow()
        self.current_sync_log = self.create_sync_log()

    def finish_sync(self):
        self.duration = datetime.utcnow() - self.start_time
        self.current_sync_log.duration = self.duration.seconds
        self.current_sync_log.save()

    def create_sync_log(self):
        previous_log_id = None if self.is_initial else self.last_sync_log._id
        last_seq = str(get_db().info()["update_seq"])
        new_synclog = SyncLog(
            user_id=self.user.user_id,
            last_seq=last_seq,
            owner_ids_on_phone=list(self.owner_ids),
            date=datetime.utcnow(),
            previous_log_id=previous_log_id
        )
        new_synclog.save(**get_safe_write_kwargs())
        return new_synclog

    @property
    def restore_class(self):
        return get_restore_class(self.domain, self.user)

    @property
    @memoized
    def loadtest_factor(self):
        return get_loadtest_factor(self.domain, self.user)


class RestoreConfig(object):
    """
    A collection of attributes associated with an OTA restore

    :param domain:          The domain object. An instance of `Domain`.
    :param user:            The mobile user requesting the restore
    :param params:          The RestoreParams associated with this (see above).
    :param cache_settings:  The RestoreCacheSettings associated with this (see above).
    """

    def __init__(self, project=None, user=None, params=None, cache_settings=None):
        self.project = project
        self.domain = project.name if project else ''
        self.user = user
        self.params = params or RestoreParams()
        self.cache_settings = cache_settings or RestoreCacheSettings()

        self.version = self.params.version
        self.restore_state = RestoreState(self.project, self.user, self.params)

        self.force_cache = self.cache_settings.force_cache
        self.cache_timeout = self.cache_settings.cache_timeout
        self.overwrite_cache = self.cache_settings.overwrite_cache

        self.cache = get_redis_default_cache()

    @property
    @memoized
    def sync_log(self):
        return self.restore_state.last_sync_log

    def validate(self):
        try:
            self.restore_state.validate_state()
        except InvalidSyncLogException, e:
            if LOOSE_SYNC_TOKEN_VALIDATION.enabled(self.domain):
                # This exception will get caught by the view and a 412 will be returned to the phone for resync
                raise RestoreException(e)
            else:
                # This exception will fail hard and we'll get a 500 error message
                raise

    def get_async_payload(self):
        if self.version == V3:
            async_response = async_restore_response.delay(self.restore_state)
            return async_response.get(timeout=10)
        else:
            return async_restore_response(self.restore_state)

    def get_payload(self):
        """
        This function currently returns either a full string payload or a string name of a file
        that contains the contents of the payload. If FILE_RESTORE toggle is enabled, then this will return
        the filename, otherwise it will return the full string payload
        """
        self.validate()

        # TODO: figure out what to do if this is a V3 retry request
        cached_response = self.get_cached_payload()
        if cached_response.exists():
            return cached_response

        self.restore_state.start_sync()

        with self.restore_state.restore_class(
                self.user.username, items=self.params.include_item_count) as response:
            normal_providers = get_restore_providers()
            for provider in normal_providers:
                for element in provider.get_elements(self.restore_state):
                    response.append(element)

            try:
                response = response + self.get_async_payload()
            except TimeoutError:
                # TODO: figure out how to cache this for the next request
                response.finalize(is_full_restore=False)
            else:
                response.finalize(is_full_restore=True)

        self.restore_state.finish_sync()
        self.set_cached_payload_if_necessary(response, self.restore_state.duration)
        return response

    def get_response(self):
        try:
            payload = self.get_payload()
            return payload.get_http_response()
        except RestoreException, e:
            logging.exception("%s error during restore submitted by %s: %s" %
                              (type(e).__name__, self.user.username, str(e)))
            response = get_simple_response_xml(
                e.message,
                ResponseNature.OTA_RESTORE_ERROR
            )
            return HttpResponse(response, mimetype="text/xml",
                                status=412)  # precondition failed

    def _initial_cache_key(self):
        return hashlib.md5('ota-restore-{user}-{version}'.format(
            user=self.user.user_id,
            version=self.version,
        )).hexdigest()

    def get_cached_payload(self):
        if self.overwrite_cache:
            return CachedResponse(None)

        if self.sync_log:
            payload = self.sync_log.get_cached_payload(self.version, stream=True)
        else:
            payload = self.cache.get(self._initial_cache_key())

        return CachedResponse(payload)

    def set_cached_payload_if_necessary(self, resp, duration):
        cache_payload = resp.get_cache_payload(bool(self.sync_log))
        if self.sync_log:
            # if there is a sync token, always cache
            try:
                data = cache_payload['data']
                self.sync_log.set_cached_payload(data, self.version)
                try:
                    data.close()
                except AttributeError:
                    pass
            except ResourceConflict:
                # if one sync takes a long time and another one updates the sync log
                # this can fail. in this event, don't fail to respond, since it's just
                # a caching optimization
                pass
        else:
            # on initial sync, only cache if the duration was longer than the threshold
            if self.force_cache or duration > timedelta(seconds=INITIAL_SYNC_CACHE_THRESHOLD):
                self.cache.set(self._initial_cache_key(), cache_payload, self.cache_timeout)
