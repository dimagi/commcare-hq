from collections import defaultdict
import itertools
import logging
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.caselogic import get_footprint
from casexml.apps.phone.data_providers.case.load_testing import append_update_to_response
from casexml.apps.phone.data_providers.case.stock import get_stock_payload
from casexml.apps.phone.data_providers.case.utils import get_case_sync_updates, CaseStub
from casexml.apps.phone.models import CaseState
from corehq.apps.hqcase.dbaccessors import iter_lite_cases_json, \
    get_n_case_ids_in_domain_by_owner
from corehq.util.dates import iso_string_to_datetime
from dimagi.utils.parsing import string_to_utc_datetime


logger = logging.getLogger(__name__)


def get_case_payload_batched(restore_state):
    response = restore_state.restore_class()

    sync_operation = BatchedCaseSyncOperation(restore_state)
    for update in sync_operation.get_all_case_updates():
        append_update_to_response(response, update, restore_state)

    sync_state = sync_operation.global_state
    restore_state.current_sync_log.cases_on_phone = sync_state.actual_owned_cases
    restore_state.current_sync_log.dependent_cases_on_phone = sync_state.actual_extended_cases

    # commtrack ledger sections
    commtrack_elements = get_stock_payload(
        restore_state.project, restore_state.stock_settings, sync_state.all_synced_cases
    )
    response.extend(commtrack_elements)

    return response, sync_operation.batch_count


class GlobalSyncState(object):
    """
    Object containing global state for a BatchedCaseSyncOperation.

    Used within the batches to ensure uniqueness of cases being synced.

    Also used after the sync is complete to provide list of CaseState objects
    """
    def __init__(self, last_sync, case_sharing=False):
        self.actual_relevant_cases_dict = {}
        self.actual_owned_cases_dict = {}
        self.all_synced_cases_dict = {}

        self.minimal_cases = {}
        if last_sync and not case_sharing:
            def state_to_case_doc(state):
                doc = state.to_json()
                doc['_id'] = state.case_id
                return doc

            self.minimal_cases = {
                state.case_id: state_to_case_doc(state) for state in itertools.chain(
                    last_sync.cases_on_phone, last_sync.dependent_cases_on_phone
                )
            }

    @property
    def actual_owned_cases(self):
        """
        Cases directly owned by the user or one of the user's groups.
        """
        return self.actual_owned_cases_dict.values()

    @property
    def actual_extended_cases(self):
        """
        Cases that are indexed by any cases owned by the user (but now owned directly)
        """
        return list(set(self.actual_relevant_cases) - set(self.actual_owned_cases))

    @property
    def actual_relevant_cases(self):
        """
        All cases relevant to the user (owned and linked to)
        """
        return self.actual_relevant_cases_dict.values()

    @property
    def all_synced_cases(self):
        """
        All cases that were included in the restore response i.e. cases that have updates
        which the phone doesn't know about
        """
        return self.all_synced_cases_dict.values()

    def update_owned_cases(self, cases):
        self.actual_owned_cases_dict.update(
            {case['_id']: CaseState.from_case(case) for case in cases}
        )

    def update_relevant_cases(self, cases):
        new_cases = []
        for case in cases:
            state = CaseState.from_case(case)
            if state.case_id not in self.actual_relevant_cases_dict:
                self.actual_relevant_cases_dict[state.case_id] = state
                new_cases.append(case)

        return new_cases

    def update_synced_cases(self, case_updates):
        self.all_synced_cases_dict.update(
            {update.case.case_id: CaseStub(update.case._id, update.case.type) for update in case_updates}
        )


class BatchedCaseSyncOperation(object):
    """
    Case Sync Operation that produces a list of CaseSyncBatch objects
    each representing a batch of CaseSyncUpdates.

    Global sync state is also available via the 'global_state' field.

    Usage:
    op = BatchedCaseSyncOperation(user, last_synclog, chunk_size)
    case_updates_generator = op.get_all_case_updates()
    list(case_updates_generator)  # consume case updates generator to update global state
    global_state = op.global_state

    Throughout this process any case should be assumed to only contain the following properties:
    '_id', 'type', 'indices', 'doc_type'.

    If 'doc_type' = CommCareCase then the case is a real case but if it is CaseState then it is
    a 'minimal case'.
    """

    # use class variable to allow patching in tests
    chunk_size = 1000

    def __init__(self, restore_state, chunk_size=None):

        self.restore_state = restore_state
        self.user = restore_state.user
        self.last_synclog = restore_state.last_sync_log
        if chunk_size:
            self.chunk_size = chunk_size

        self.domain = self.restore_state.domain

        try:
            self.owner_ids = list(self.restore_state.owner_ids)
        except AttributeError:
            self.owner_ids = [self.user.user_id]

        self.case_sharing = len(self.owner_ids) > 1
        self.global_state = GlobalSyncState(self.last_synclog, self.case_sharing)
        self.batch_count = 0

    def batches(self):
        for owner_id in self.owner_ids:
            batch = CaseSyncCouchBatch(
                self.global_state,
                self.domain,
                self.last_synclog,
                self.chunk_size,
                owner_id,
                case_sharing=self.case_sharing
            )
            yield batch
            while batch.next_batch:
                batch = batch.next_batch
                yield batch

        if self.last_synclog:
            yield CaseSyncPhoneBatch(
                self.global_state,
                self.domain,
                self.last_synclog,
                self.chunk_size,
                case_sharing=self.case_sharing
            )

    def get_all_case_updates(self):
        """
        Returns a generator that yields the case updates for this user.
        Iterating through the updates also has the effect of updating this object's GlobalSyncState.
        """
        def get_updates(batch):
            self.batch_count += 1
            return batch.case_updates_to_sync()

        return itertools.chain.from_iterable(get_updates(batch) for batch in self.batches())


class CaseSyncBatch(object):
    """
    Object representing a batch of case updates to sync.
    """
    def __init__(self, global_state, domain, last_sync, chunksize, case_sharing):
        self.global_state = global_state
        self.domain = domain
        self.last_sync = last_sync
        self.chunksize = chunksize
        self.case_sharing = case_sharing
        self.next_batch = None

    @property
    def case_updates_to_sync(self):
        """
        Override this to return the list of cases to sync
        """
        return []

    def _get_potential_cases(self, cases):
        return filter_cases_modified_elsewhere_since_sync(list(cases), self.last_sync)

    def _case_sync_updates(self, all_potential_to_sync):
        return get_case_sync_updates(self.domain, all_potential_to_sync, self.last_sync)

    def _fetch_missing_cases_and_wrap(self, casedoc_list):
        cases = []
        to_fetch = []
        for doc in casedoc_list:
            if doc['doc_type'] == 'CommCareCase':
                cases.append(CommCareCase.wrap(doc))
            else:
                to_fetch.append(doc['_id'])

        cases.extend(CommCareCase.bulk_get_lite(to_fetch, wrap=True, chunksize=self.chunksize))
        return cases


class CaseSyncPhoneBatch(CaseSyncBatch):
    """
    Batch of updates representing all cases that are on the phone
    but aren't part of the 'owned' cases of the user.
    """
    def __init__(self, global_state, domain, last_sync, chunksize, case_sharing=False):
        super(CaseSyncPhoneBatch, self).__init__(global_state, domain, last_sync, chunksize, case_sharing)

        # case sharing is in use so we need to fetch the cases from the DB in case
        # they were modified by another user or reference cases owned by another user
        self.use_minimal_cases = not self.case_sharing

    def case_updates_to_sync(self):
        other_case_ids_on_phone = set([
            case_id
            for case_id in self.last_sync.get_footprint_of_cases_on_phone()
            if case_id not in self.global_state.actual_relevant_cases_dict
        ])

        logger.debug("%s other cases on phone", len(other_case_ids_on_phone))
        if not other_case_ids_on_phone:
            return []

        if self.use_minimal_cases:
            other_cases_on_phone = [
                self.global_state.minimal_cases[case_id] for case_id in other_case_ids_on_phone
            ]
        else:
            other_cases_on_phone = CommCareCase.bulk_get_lite(
                other_case_ids_on_phone,
                wrap=False,
                chunksize=len(other_case_ids_on_phone)
            )

        potential_to_sync = self._get_potential_cases(other_cases_on_phone)
        cases_to_sync = self._fetch_missing_cases_and_wrap(potential_to_sync)
        case_sync_updates = self._case_sync_updates(cases_to_sync)

        self.global_state.update_synced_cases(case_sync_updates)
        return case_sync_updates

    def __repr__(self):
        return "CaseSyncPhoneBatch(use_minimal_cases={})".format(
            self.use_minimal_cases
        )


class CaseSyncCouchBatch(CaseSyncBatch):
    """
    Batch of case updates for cases 'owned' by the user.
    """
    def __init__(self, global_state, domain, last_sync, chunksize,
                 owner_id, case_sharing=False, startkey_docid=None):
        super(CaseSyncCouchBatch, self).__init__(global_state, domain, last_sync, chunksize, case_sharing)
        self.owner_id = owner_id
        self.startkey_docid = startkey_docid

        # We can only use minimal cases if:
        # * there is a SyncLog which we can use that has cases in it
        # * the user is not part of any case sharing groups
        self.use_minimal_cases = self.last_sync and not case_sharing

    def case_updates_to_sync(self):
        actual_owned_cases = self._actual_owned_cases()
        if not actual_owned_cases:
            return []

        self.global_state.update_owned_cases(actual_owned_cases)

        all_relevant_cases_dict = self._all_relevant_cases_dict(actual_owned_cases)
        actual_relevant_cases = self.global_state.update_relevant_cases(all_relevant_cases_dict.values())

        potential_to_sync = self._get_potential_cases(actual_relevant_cases)

        cases_to_sync = self._fetch_missing_cases_and_wrap(potential_to_sync)
        case_sync_updates = self._case_sync_updates(cases_to_sync)
        self.global_state.update_synced_cases(case_sync_updates)

        return case_sync_updates

    def _get_case_ids(self):
        case_ids = get_n_case_ids_in_domain_by_owner(
            self.domain, self.owner_id, self.chunksize, self.startkey_docid)

        for case_id in case_ids:
            yield case_id

        if len(case_ids) >= self.chunksize:
            self.next_batch = CaseSyncCouchBatch(
                self.global_state,
                self.domain,
                self.last_sync,
                self.chunksize,
                self.owner_id,
                self.case_sharing,
                startkey_docid=case_ids[-1]
            )

    def _actual_owned_cases(self):
        """
        This returns a list of case dicts. Each dict will either be an actual case dict or else
        a dict containing only these keys: '_id', 'type', 'indices'. These 'minimal cases' are
        created from CaseState objects from the previous SyncLog.
        """
        def _case_domain_match(case):
            return not self.domain or self.domain == case.get('domain')

        case_ids = self._get_case_ids()
        if self.use_minimal_cases:
            # First we check to see if there is a case state available that we can use
            # rather than fetching the whole case.
            minimal_cases = []
            cases_to_fetch = []
            for case_id in case_ids:
                minimal_case = self.global_state.minimal_cases.get(case_id)
                if minimal_case:
                    minimal_cases.append(minimal_case)
                else:
                    cases_to_fetch.append(case_id)

            logger.debug(
                "%s cases found in previous SyncLog. %s still to fetch",
                len(minimal_cases), len(cases_to_fetch)
            )

            if cases_to_fetch:
                cases = CommCareCase.bulk_get_lite(cases_to_fetch, wrap=False, chunksize=self.chunksize)
                minimal_cases.extend(
                    case_doc for case_doc in cases
                    if _case_domain_match(case_doc)
                )
            return minimal_cases
        else:
            lite_cases = list(iter_lite_cases_json(case_ids, self.chunksize))
            logger.debug("No previous SyncLog. Fetched %s cases", len(lite_cases))
            return lite_cases

    def _all_relevant_cases_dict(self, cases):
        return get_footprint(cases, domain=self.domain, strip_history=True)

    def __repr__(self):
        return "CaseSyncCouchBatch(startkey={}, startkey_docid={}, chunksize={}, use_minimal_cases={})".format(
            self.owner_id,
            self.startkey_docid,
            self.chunksize,
            self.use_minimal_cases
        )


def filter_cases_modified_elsewhere_since_sync(cases, last_sync_token):
    """
    This function takes in a list of unwrapped case dicts and a last_sync token and
    returns the set of cases that should be applicable to be sent down on top of that
    sync token.

    This includes:

      1. All cases that were modified since the last sync date by any phone other
         than the phone that is associated with the sync token.
      2. All cases that were not on the phone at the time of last sync that are
         now on the phone.
    """
    # todo: this function is pretty ugly and is heavily optimized to reduce the number
    # of queries to couch.
    if not last_sync_token:
        return cases
    else:
        # we can start by filtering out our base set of cases to check for only
        # things that have been modified since we last synced
        def _is_relevant(case_or_case_state_dict):
            if case_or_case_state_dict:
                # only case-like things have this.
                if 'server_modified_on' in case_or_case_state_dict:
                    return string_to_utc_datetime(case['server_modified_on']) >= last_sync_token.date
            # for case states default to always checking for recent updates
            return True

        recently_modified_case_ids = [case['_id'] for case in cases if _is_relevant(case)]
        # create a mapping of all cases to sync logs for all cases that were modified
        # in the appropriate ranges.
        # todo: this should really have a better way to filter out updates from sync logs
        # that we already have in a better way.
        # todo: if this recently modified case list is huge i'm guessing this query is
        # pretty expensive
        case_log_map = CommCareCase.get_db().view(
            'phone/cases_to_sync_logs',
            keys=recently_modified_case_ids,
            reduce=False,
        )

        unique_combinations = set((row['key'], row['value']) for row in case_log_map)

        # todo: and this one is also going to be very bad. see note above about how we might
        # be able to reduce it - by finding a way to only query for sync tokens that are more
        # likely to be relevant.
        modification_dates = CommCareCase.get_db().view(
            'phone/case_modification_status',
            keys=[list(combo) for combo in unique_combinations],
            reduce=True,
            group=True,
        )
        # we'll build a structure that looks like this for efficiency:
        # { case_id: [{'token': 'token value', 'date': 'date value'}, ...]}
        all_case_updates_by_sync_token = defaultdict(list)
        for row in modification_dates:
            # format from couch is a list of objects that look like this:
            # {
            #   'value': '2012-08-22T08:55:14Z', (most recent date updated)
            #   'key': ['case-id', 'sync-token-id']
            # }
            if row['value']:
                modification_date = iso_string_to_datetime(row['value'])
                if modification_date >= last_sync_token.date:
                    case_id, sync_token_id = row['key']
                    all_case_updates_by_sync_token[case_id].append(
                        {'token': sync_token_id, 'date': modification_date}
                    )

        def case_modified_elsewhere_since_sync(case_id):
            # NOTE: uses closures
            return any([row['date'] >= last_sync_token.date and row['token'] != last_sync_token._id
                        for row in all_case_updates_by_sync_token[case_id]])

        def relevant(case):
            case_id = case['_id']
            return (case_modified_elsewhere_since_sync(case_id)
                    or not last_sync_token.phone_is_holding_case(case_id))

        return filter(relevant, cases)
