from StringIO import StringIO
from io import FileIO
from os import path
import os
from uuid import uuid4
from collections import defaultdict
from copy import deepcopy
import shutil
import hashlib
import tempfile
from couchdbkit import ResourceConflict, ResourceNotFound
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.caselogic import BatchedCaseSyncOperation, CaseSyncUpdate
from casexml.apps.phone.data_providers import get_restore_providers, get_long_running_providers
from casexml.apps.phone.exceptions import (
    MissingSyncLog, InvalidSyncLogException, SyncLogUserMismatch,
    BadStateException, RestoreException,
)
from casexml.apps.stock.consumption import compute_consumption_or_default
from casexml.apps.stock.utils import get_current_ledger_transactions_multi
from corehq.toggles import LOOSE_SYNC_TOKEN_VALIDATION, FILE_RESTORE, STREAM_RESTORE_CACHE, ENABLE_LOADTEST_USERS
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.phone.models import SyncLog
import logging
from dimagi.utils.couch.database import get_db, get_safe_write_kwargs
from casexml.apps.phone import xml
from datetime import datetime, timedelta
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from couchforms.xml import (
    ResponseNature,
    get_simple_response_xml,
)
from casexml.apps.case.xml import check_version, V1
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


def stream_response(payload, is_file=True):
    try:
        if is_file:
            response = StreamingHttpResponse(FileWrapper(open(payload, 'r')), mimetype="text/xml")
            response['Content-Length'] = os.path.getsize(payload)
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
        any consumption data set in the restore
        """
        self.section_to_consumption_types = section_to_consumption_types or {}
        self.consumption_config = consumption_config
        self.default_product_list = default_product_list or []
        self.force_consumption_case_filter = force_consumption_case_filter or (lambda case: False)


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
            self.response_body.write(xml.tostring(xml_element))

    def extend(self, iterable):
        for element in iterable:
            self.append(element)

    def finalize(self):
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
        payload_dir = getattr(settings, 'RESTORE_PAYLOAD_DIR', None)
        self.filename = path.join(payload_dir or tempfile.gettempdir(), uuid4().hex)

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

    def get_cache_payload(self, full=False):
        return {
            'is_file': True,
            'data': self.get_filename() if not full else open(self.get_filename(), 'r')
        }

    def as_string(self):
        with open(self.get_filename(), 'r') as f:
            return f.read()

    def get_http_response(self):
        return stream_response(self.get_filename())


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


def get_stock_payload(domain, stock_settings, case_state_list):
    if domain and not domain.commtrack_enabled:
        return

    from lxml.builder import ElementMaker
    E = ElementMaker(namespace=COMMTRACK_REPORT_XMLNS)

    def entry_xml(id, quantity):
        return E.entry(
            id=id,
            quantity=str(int(quantity)),
        )

    def transaction_to_xml(trans):
        return entry_xml(trans.product_id, trans.stock_on_hand)

    def consumption_entry(case_id, product_id, section_id):
        consumption_value = compute_consumption_or_default(
            case_id,
            product_id,
            datetime.utcnow(),
            section_id,
            stock_settings.consumption_config
        )
        if consumption_value is not None:
            return entry_xml(product_id, consumption_value)

    case_ids = [case.case_id for case in case_state_list]
    all_current_ledgers = get_current_ledger_transactions_multi(case_ids)
    for commtrack_case in case_state_list:
        case_id = commtrack_case.case_id
        current_ledgers = all_current_ledgers[case_id]

        section_product_map = defaultdict(lambda: [])
        section_timestamp_map = defaultdict(lambda: json_format_datetime(datetime.utcnow()))
        for section_id in sorted(current_ledgers.keys()):
            transactions_map = current_ledgers[section_id]
            sorted_product_ids = sorted(transactions_map.keys())
            transactions = [transactions_map[p] for p in sorted_product_ids]
            as_of = json_format_datetime(max(txn.report.date for txn in transactions))
            section_product_map[section_id] = sorted_product_ids
            section_timestamp_map[section_id] = as_of
            yield E.balance(*(transaction_to_xml(e) for e in transactions),
                            **{'entity-id': case_id, 'date': as_of, 'section-id': section_id})

        for section_id, consumption_section_id in stock_settings.section_to_consumption_types.items():

            if (section_id in current_ledgers or
                    stock_settings.force_consumption_case_filter(commtrack_case)):

                consumption_product_ids = stock_settings.default_product_list \
                    if stock_settings.default_product_list \
                    else section_product_map[section_id]

                consumption_entries = filter(lambda e: e is not None, [
                    consumption_entry(case_id, p, section_id)
                    for p in consumption_product_ids
                ])

                if consumption_entries:
                    yield E.balance(
                        *consumption_entries,
                        **{
                            'entity-id': case_id,
                            'date': section_timestamp_map[section_id],
                            'section-id': consumption_section_id,
                        }
                    )


def get_restore_class(user):
    restore_class = StringRestoreResponse
    if FILE_RESTORE.enabled(user.domain) or FILE_RESTORE.enabled(user.username):
        restore_class = FileRestoreResponse

    return restore_class


def _get_loadtest_factor(domain, user):
    """
    Gets the loadtest factor for a domain and user. Is always 1 unless
    both the toggle is enabled for the domain, and the user has a non-zero,
    non-null factor set.
    """
    if domain and ENABLE_LOADTEST_USERS.enabled(domain.name):
        return getattr(user, 'loadtest_factor', 1) or 1
    return 1


def _transform_loadtest_update(update, factor):
    """
    Returns a new CaseSyncUpdate object (from an existing one) with all the
    case IDs and names mapped to have the factor appended.
    """
    def _map_id(id, count):
        return '{}-{}'.format(id, count)
    case = CommCareCase.wrap(deepcopy(update.case._doc))
    case._id = _map_id(case._id, factor)
    for index in case.indices:
        index.referenced_id = _map_id(index.referenced_id, factor)
    case.name = '{} ({})'.format(case.name, factor)
    return CaseSyncUpdate(case, update.sync_token, required_updates=update.required_updates)


def get_case_payload_batched(domain, stock_settings, version, user, last_synclog, new_synclog):
    response = get_restore_class(user)()

    sync_operation = BatchedCaseSyncOperation(user, last_synclog)
    factor = _get_loadtest_factor(domain, user)
    for update in sync_operation.get_all_case_updates():
        current_count = 0
        original_update = update
        while current_count < factor:
            element = xml.get_case_element(update.case, update.required_updates, version)
            response.append(element)
            current_count += 1
            if current_count < factor:
                update = _transform_loadtest_update(original_update, current_count)

    sync_state = sync_operation.global_state
    new_synclog.cases_on_phone = sync_state.actual_owned_cases
    new_synclog.dependent_cases_on_phone = sync_state.actual_extended_cases
    new_synclog.save(**get_safe_write_kwargs())

    # commtrack balance sections
    commtrack_elements = get_stock_payload(domain, stock_settings, sync_state.all_synced_cases)
    response.extend(commtrack_elements)

    return response, sync_operation.batch_count


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
    def __init__(self, domain, user, params):
        self.domain = domain
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
                sync_log = SyncLog.get(self.params.sync_log_id)
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
            owner_ids_on_phone=self.user.get_owner_ids(),
            date=datetime.utcnow(),
            previous_log_id=previous_log_id
        )
        new_synclog.save(**get_safe_write_kwargs())
        return new_synclog

    @property
    def restore_class(self):
        return get_restore_class(self.user)


class RestoreConfig(object):
    """
    A collection of attributes associated with an OTA restore

    :param domain:          The domain object. An instance of `Domain`.
    :param user:            The mobile user requesting the restore
    :param params:          The RestoreParams associated with this (see above).
    :param cache_settings:  The RestoreCacheSettings associated with this (see above).
    """

    def __init__(self, domain=None, user=None, params=None, cache_settings=None):
        self.domain = domain
        self.user = user
        self.params = params or RestoreParams()
        self.cache_settings = cache_settings or RestoreCacheSettings()

        self.version = self.params.version
        self.restore_state = RestoreState(self.domain, self.user, self.params)

        self.domain = domain
        self.force_cache = self.cache_settings.force_cache
        self.cache_timeout = self.cache_settings.cache_timeout
        self.overwrite_cache = self.cache_settings.overwrite_cache

        self.cache = get_redis_default_cache()

        # keep track of the number of batches (if any) for comparison in unit tests
        self.num_batches = None

    @property
    @memoized
    def sync_log(self):
        return self.restore_state.last_sync_log

    def validate(self):
        try:
            self.restore_state.validate_state()
        except InvalidSyncLogException, e:
            if LOOSE_SYNC_TOKEN_VALIDATION.enabled(self.domain.name):
                # This exception will get caught by the view and a 412 will be returned to the phone for resync
                raise RestoreException(e)
            else:
                # This exception will fail hard and we'll get a 500 error message
                raise

    def get_payload(self):
        """
        This function currently returns either a full string payload or a string name of a file
        that contains the contents of the payload. If FILE_RESTORE toggle is enabled, then this will return
        the filename, otherwise it will return the full string payload
        """
        self.validate()

        cached_response = self.get_cached_payload()
        if cached_response.exists():
            return cached_response

        user = self.user
        # create a sync log for this
        self.restore_state.start_sync()

        # start with standard response
        with self.restore_state.restore_class(user.username, items=self.params.include_item_count) as response:
            normal_providers = get_restore_providers()
            for provider in normal_providers:
                for element in provider.get_elements(self.restore_state):
                    response.append(element)

            # in the future these will be done asynchronously so keep them separate
            long_running_providers = get_long_running_providers()
            for provider in long_running_providers:
                partial_response = provider.get_response(self.restore_state)
                response = response + partial_response
                partial_response.close()

            response.finalize()

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
            stream = STREAM_RESTORE_CACHE.enabled(self.user.domain)
            payload = self.sync_log.get_cached_payload(self.version, stream=stream)
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
