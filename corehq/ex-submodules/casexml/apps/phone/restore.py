from StringIO import StringIO
from collections import defaultdict
import hashlib
from couchdbkit import ResourceConflict
from casexml.apps.phone.caselogic import BatchedCaseSyncOperation
from casexml.apps.stock.consumption import compute_consumption_or_default
from casexml.apps.stock.utils import get_current_ledger_transactions_multi
from corehq.toggles import BATCHED_RESTORE
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.case.exceptions import BadStateException, RestoreException
from casexml.apps.phone.models import SyncLog, CaseState
import logging
from dimagi.utils.couch.database import get_db, get_safe_write_kwargs
from casexml.apps.phone import xml
from datetime import datetime, timedelta
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from couchforms.xml import (
    ResponseNature,
    get_response_element,
    get_simple_response_xml,
)
from casexml.apps.case.xml import check_version, V1
from casexml.apps.phone.fixtures import generator
from django.http import HttpResponse
from casexml.apps.phone.checksum import CaseStateHash
from no_exceptions.exceptions import HttpException

logger = logging.getLogger(__name__)

# how long a cached payload sits around for (in seconds).
INITIAL_SYNC_CACHE_TIMEOUT = 60 * 60  # 1 hour

# the threshold for setting a cached payload on initial sync (in seconds).
# restores that take less than this time will not be cached to allow
# for rapid iteration on fixtures/cases/etc.
INITIAL_SYNC_CACHE_THRESHOLD = 60  # 1 minute


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


class EtreeRestoreResponse(object):
    def __init__(self, username, items=False):
        self.items = items
        self.response = get_response_element(
            "Successfully restored account %s!" % username,
            ResponseNature.OTA_RESTORE_SUCCESS)

    def append(self, xml):
        self.response.append(xml)

    def __str__(self):
        if self.items:
            self.response.attrib['items'] = '%d' % len(self.response.getchildren())
        return xml.tostring(self.response)


class StringRestoreResponse(object):
    start_tag_template = '<OpenRosaResponse xmlns="http://openrosa.org/http/response"{items}>'
    items_template = ' items="{}"'
    message_template = '<message nature="{nature}">{message}</message>'
    closing_tag = '</OpenRosaResponse>'

    def __init__(self, username, items=False):
        self.items = items
        self.num_items = 0
        self.response = StringIO()
        self.append(self.message_template.format(
            message="Successfully restored account %s!" % username,
            nature=ResponseNature.OTA_RESTORE_SUCCESS
        ))

    def append(self, xml_element):
        self.num_items += 1
        if isinstance(xml_element, basestring):
            self.response.write(xml_element)
        else:
            self.response.write(xml.tostring(xml_element))

    def __str__(self):
        items = self.items_template.format(self.num_items) if self.items else ''
        return '{start}{body}{end}'.format(
            start=self.start_tag_template.format(items=items),
            body=self.response.getvalue(),
            end=self.closing_tag
        )


class RestoreConfig(object):
    """
    A collection of attributes associated with an OTA restore

    :param user:            The mobile user requesting the restore
    :param restore_id:      ID of the previous restore
    :param version:         The version of the restore format
    :param state_hash:      The case state hash string to use to verify the state of the phone
    :param items:           Set to `True` to include the item count in the response
    :param stock_settings:  CommTrack stock settings for the domain.
                            If None, default settings will be used.
    :param domain:          The domain object. An instance of `Domain`.
    :param force_cache:     Set to `True` to force the response to be cached.
                            Only applies if `restore_id` is empty.
    :param cache_timeout:   Override the default cache timeout of 1 hour.
                            Only applies if `restore_id` is empty.
    :param overwrite_cache: Ignore any previously cached value and re-generate the restore response.
                            Only applies if `restore_id` is empty.
    """
    def __init__(self, user, restore_id="", version=V1, state_hash="",
                 items=False, stock_settings=None, domain=None, force_cache=False,
                 cache_timeout=None, overwrite_cache=False):
        self.user = user
        self.restore_id = restore_id
        self.version = version
        self.state_hash = state_hash
        self.items = items
        self.stock_settings = stock_settings or StockSettings()
        self.domain = domain
        self.force_cache = force_cache
        self.cache_timeout = cache_timeout or INITIAL_SYNC_CACHE_TIMEOUT
        self.overwrite_cache = overwrite_cache

        self.cache = get_redis_default_cache()

    @property
    @memoized
    def sync_log(self):
        if self.restore_id:
            sync_log = SyncLog.get(self.restore_id)
            if sync_log.user_id == self.user.user_id \
                    and sync_log.doc_type == 'SyncLog':
                return sync_log
            else:
                raise HttpException(412)
        else:
            return None

    def validate(self):
        # runs validation checks, raises exceptions if anything is amiss
        check_version(self.version)
        if self.sync_log and self.state_hash:
            parsed_hash = CaseStateHash.parse(self.state_hash)
            if self.sync_log.get_state_hash() != parsed_hash:
                raise BadStateException(expected=self.sync_log.get_state_hash(),
                                        actual=parsed_hash,
                                        case_ids=self.sync_log.get_footprint_of_cases_on_phone())

    def get_stock_payload(self, case_state_list):
        if self.domain and not self.domain.commtrack_enabled:
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
                self.stock_settings.consumption_config
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

            for section_id, consumption_section_id in self.stock_settings.section_to_consumption_types.items():

                if (section_id in current_ledgers or
                        self.stock_settings.force_consumption_case_filter(commtrack_case)):

                    consumption_product_ids = self.stock_settings.default_product_list \
                        if self.stock_settings.default_product_list \
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

    def get_payload(self):
        user = self.user
        last_sync = self.sync_log

        self.validate()

        cached_payload = self.get_cached_payload()
        if cached_payload:
            return cached_payload

        start_time = datetime.utcnow()
        last_seq = str(get_db().info()["update_seq"])

        # create a sync log for this
        previous_log_id = last_sync.get_id if last_sync else None
        synclog = SyncLog(
            user_id=user.user_id,
            last_seq=last_seq,
            owner_ids_on_phone=user.get_owner_ids(),
            date=datetime.utcnow(),
            previous_log_id=previous_log_id
        )
        synclog.save(**get_safe_write_kwargs())

        # start with standard response
        batch_enabled = BATCHED_RESTORE.enabled(self.user.domain) or BATCHED_RESTORE.enabled(self.user.username)
        logger.debug('Batch restore enabled: %s', batch_enabled)
        if batch_enabled:
            response = StringRestoreResponse(user.username, items=self.items)
        else:
            response = EtreeRestoreResponse(user.username, items=self.items)

        # add sync token info
        response.append(xml.get_sync_element(synclog.get_id))
        # registration block
        response.append(xml.get_registration_element(user))

        # fixture block
        for fixture in generator.get_fixtures(user, self.version, last_sync):
            response.append(fixture)

        payload_fn = self._get_case_payload_batched if batch_enabled else self._get_case_payload
        response = payload_fn(response, user, last_sync, synclog)

        resp = str(response)
        duration = datetime.utcnow() - start_time
        synclog.duration = duration.seconds
        synclog.save()
        self.set_cached_payload_if_necessary(resp, duration)
        return resp

    def _get_case_payload(self, response, user, last_sync, synclog):
        sync_operation = user.get_case_updates(last_sync)
        synclog.cases_on_phone = [
            CaseState.from_case(c) for c in sync_operation.actual_owned_cases
        ]
        synclog.dependent_cases_on_phone = [
            CaseState.from_case(c) for c in sync_operation.actual_extended_cases
        ]
        synclog.save(**get_safe_write_kwargs())

        # case blocks
        case_xml_elements = (
            xml.get_case_element(op.case, op.required_updates, self.version)
            for op in sync_operation.actual_cases_to_sync
        )
        for case_elem in case_xml_elements:
            response.append(case_elem)

        # commtrack balance sections
        case_state_list = [CaseState.from_case(op.case) for op in sync_operation.actual_cases_to_sync]
        commtrack_elements = self.get_stock_payload(case_state_list)
        for ct_elem in commtrack_elements:
            response.append(ct_elem)

        return response

    def _get_case_payload_batched(self, response, user, last_sync, synclog):
        synclog.save(**get_safe_write_kwargs())

        sync_operation = BatchedCaseSyncOperation(user, last_sync)
        for batch in sync_operation.batches():
            logger.debug(batch)

            # case blocks
            case_xml_elements = (
                xml.get_case_element(op.case, op.required_updates, self.version)
                for op in batch.case_updates_to_sync
            )
            for case_elem in case_xml_elements:
                response.append(case_elem)

        sync_state = sync_operation.global_state
        synclog.cases_on_phone = sync_state.actual_owned_cases
        synclog.dependent_cases_on_phone = sync_state.actual_extended_cases
        synclog.save(**get_safe_write_kwargs())

        # commtrack balance sections
        commtrack_elements = self.get_stock_payload(sync_state.all_synced_cases)
        for ct_elem in commtrack_elements:
            response.append(ct_elem)

        return response

    def get_response(self):
        try:
            return HttpResponse(self.get_payload(), mimetype="text/xml")
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
            return

        if self.sync_log:
            return self.sync_log.get_cached_payload(self.version)
        else:
            return self.cache.get(self._initial_cache_key())

    def set_cached_payload_if_necessary(self, resp, duration):
        if self.sync_log:
            # if there is a sync token, always cache
            try:
                self.sync_log.set_cached_payload(resp, self.version)
            except ResourceConflict:
                # if one sync takes a long time and another one updates the sync log
                # this can fail. in this event, don't fail to respond, since it's just
                # a caching optimization
                pass
        else:
            # on initial sync, only cache if the duration was longer than the threshold
            if self.force_cache or duration > timedelta(seconds=INITIAL_SYNC_CACHE_THRESHOLD):
                self.cache.set(self._initial_cache_key(), resp, self.cache_timeout)


def generate_restore_payload(user, restore_id="", version=V1, state_hash="",
                             items=False):
    """
    Gets an XML payload suitable for OTA restore. If you need to do something
    other than find all cases matching user_id = user.user_id then you have
    to pass in a user object that overrides the get_case_updates() method.

    It should match the same signature as models.user.get_case_updates():

        user:          who the payload is for. must implement get_case_updates
        restore_id:    sync token
        version:       the CommCare version

        returns: the xml payload of the sync operation
    """
    config = RestoreConfig(user, restore_id, version, state_hash, items=items)
    return config.get_payload()


def generate_restore_response(user, restore_id="", version=V1, state_hash="",
                              items=False):
    config = RestoreConfig(user, restore_id, version, state_hash, items=items)
    return config.get_response()
