"""
Logic about chws phones and cases go here.
"""
from collections import defaultdict
from datetime import datetime
import itertools
import logging
from casexml.apps.case.models import CommCareCase
from casexml.apps.case import const
from casexml.apps.case.util import reverse_indices
from casexml.apps.case.xform import CaseDbCache
from casexml.apps.phone.models import CaseState
from dimagi.utils.decorators.memoized import memoized

logger = logging.getLogger(__name__)


def get_related_cases(initial_case_list, domain, strip_history=False, search_up=True):
    """
    Gets the flat list of related cases based on a starting list.
    Walks all the referenced indexes recursively.
    If search_up is True, all cases and their parent cases are returned.
    If search_up is False, all cases and their child cases are returned.
    """
    if not initial_case_list:
        return {}

    # todo: should assert that domain exists here but this breaks tests
    case_db = CaseDbCache(domain=domain,
                          strip_history=strip_history,
                          deleted_ok=True,
                          initial=initial_case_list)

    def related(case_db, case):
        return [case_db.get(index['referenced_id']) for index in (
            case['indices'] if search_up else reverse_indices(case, wrap=False))]

    relevant_cases = {}
    relevant_deleted_case_ids = []

    queue = list(case for case in initial_case_list)
    directly_referenced_indices = itertools.chain(
        *[[index['referenced_id'] for index in (
            case['indices'] if search_up else reverse_indices(case, wrap=False))]
          for case in initial_case_list]
    )
    case_db.populate(directly_referenced_indices)
    while queue:
        case = queue.pop()
        if case and case['_id'] not in relevant_cases:
            relevant_cases[case['_id']] = case
            if case['doc_type'] == 'CommCareCase-Deleted':
                relevant_deleted_case_ids.append(case['_id'])
            queue.extend(related(case_db, case))

    if relevant_deleted_case_ids:
        logging.info('deleted cases included in footprint (restore): %s' % (
            ', '.join(relevant_deleted_case_ids)
        ))

    return relevant_cases
    # print 'relevant', len(relevant_cases)
    # return [CommCareCase.wrap(c) for c in relevant_cases]


def get_footprint(initial_case_list, domain, strip_history=False):
    return get_related_cases(initial_case_list, domain, strip_history=strip_history, search_up=True)

class CaseSyncUpdate(object):
    """
    The record of how a case should sync
    """
    def __init__(self, case, sync_token):
        self.case = case
        self.sync_token = sync_token
        # cache this property since computing it can be expensive
        self.required_updates = self._get_required_updates()
        
    
    def _get_required_updates(self):
        """
        Returns a list of the required updates for this case/token
        pairing. Should be a list of actions like [create, update, close]
        """
        ret = []
        if not self.sync_token or not self.sync_token.phone_has_case(self.case.get_id):
            ret.append(const.CASE_ACTION_CREATE)
        # always include an update 
        ret.append(const.CASE_ACTION_UPDATE)
        if self.case.closed:
            ret.append(const.CASE_ACTION_CLOSE)
        return ret


def _to_case_id_set(cases):
    return set([c.case_id for c in cases])


class CaseSyncOperation(object):
    """
    A record of a user's sync operation
    """
    
    def __init__(self, user, last_sync):
        self.user = user
        self.last_sync = last_sync

    @property
    @memoized
    def actual_owned_cases(self):
        try:
            keys = [[owner_id, False] for owner_id in self.user.get_owner_ids()]
        except AttributeError:
            keys = [[self.user.user_id, False]]

        def _user_case_domain_match(case):
            if self.user.domain:
                return self.user.domain == case.domain
            return True

        cases = CommCareCase.view("case/by_owner_lite", keys=keys).all()
        return set(filter(_user_case_domain_match, cases))

    @property
    @memoized
    def actual_cases_to_sync(self):
        # the world to sync involves
        # Union(cases on the phone, footprint of those,
        #       cases the server thinks are the phone's, footprint of those)
        # intersected with:
        # (cases modified by someone else since the last sync)

        # TODO: clean this up. Basically everything is a set of cases,
        # but in order to do proper comparisons we use IDs so all of these
        # operations look much more complicated than they should be.
        actual_cases_to_sync = []
        for _, case in self.all_potential_to_sync_dict.items():
            sync_update = CaseSyncUpdate(case, self.last_sync)
            if sync_update.required_updates:
                actual_cases_to_sync.append(sync_update)

        return actual_cases_to_sync

    @property
    @memoized
    def _all_relevant_cases(self):
        return get_footprint(self.actual_owned_cases, domain=self.user.domain)

    @property
    @memoized
    def actual_relevant_cases(self):
        return set(self._all_relevant_cases.values())

    @property
    @memoized
    def actual_extended_cases(self):
        return set([
            self._get_case(case_id) for case_id in
            _to_case_id_set(self.actual_relevant_cases) -
            _to_case_id_set(self.actual_owned_cases)
        ])

    @property
    @memoized
    def phone_relevant_cases(self):
        return set([
            self._get_case(case_id) for case_id
            in self.last_sync.get_footprint_of_cases_on_phone()
        ]) if self.last_sync else set()

    @property
    @memoized
    def all_potential_cases(self):
        return set([
            self._get_case(case_id) for case_id in
            _to_case_id_set(self.actual_relevant_cases) |
            _to_case_id_set(self.phone_relevant_cases)
        ])

    @property
    @memoized
    def all_potential_to_sync(self):
        return filter_cases_modified_elsewhere_since_sync(list(self.all_potential_cases), self.last_sync)

    @property
    @memoized
    def all_potential_to_sync_dict(self):
        # this is messy but forces uniqueness at the case_id level, without
        # having to reload all the cases from the DB
        return dict((case.get_id, case) for case in self.all_potential_to_sync)

    def _get_case(self, case_id):
        if case_id in self._all_relevant_cases:
            return self._all_relevant_cases[case_id]
        else:
            case = CommCareCase.get_with_rebuild(case_id)
            self._all_relevant_cases[case_id] = case
            return case


class GlobalSyncState(object):
    """
    Object containing global state for a BatchedCaseSyncOperation.

    Used within the batches to ensure uniqueness of cases being synced.

    Also used after the sync is complete to provide list of CaseState objects
    """
    def __init__(self):
        self.actual_relevant_cases_dict = {}
        self.actual_owned_cases_dict = {}
        self.all_synced_cases_dict = {}

    @property
    def actual_owned_cases(self):
        return self.actual_owned_cases_dict.values()

    @property
    def actual_extended_cases(self):
        return list(set(self.actual_relevant_cases) - set(self.actual_owned_cases))

    @property
    def actual_relevant_cases(self):
        return self.actual_relevant_cases_dict.values()

    @property
    def all_synced_cases(self):
        return self.all_synced_cases_dict.values()

    def update_owned_cases(self, cases):
        self.actual_owned_cases_dict.update(
            {case.case_id: CaseState.from_case(case) for case in cases}
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
            {update.case.case_id: CaseState.from_case(update.case) for update in case_updates}
        )


class BatchedCaseSyncOperation(object):
    """
    Case Sync Operation that produces a list of CaseSyncBatch objects
    each representing a batch of CaseSyncUpdates.

    Global sync state is also available via the 'global_state' field.

    Usage:
    op = BatchedCaseSyncOperation(user, last_sync, chunk_size)
    for batch in op.batches():
        case_updates = batch.case_updates_to_sync

    global_state = op.global_state
    """
    def __init__(self, user, last_sync, chunk_size=1000):
        self.user = user
        self.last_sync = last_sync
        self.chunk_size = chunk_size
        self.domain = self.user.domain
        self.global_state = GlobalSyncState()

        try:
            self.owner_keys = [[owner_id, False] for owner_id in self.user.get_owner_ids()]
        except AttributeError:
            self.owner_keys = [[self.user.user_id, False]]

    def batches(self):
        for key in self.owner_keys:
            batch = CaseSyncCouchBatch(
                self.global_state,
                self.domain,
                self.last_sync,
                self.chunk_size,
                key
            )
            yield batch
            while batch.next_batch:
                batch = batch.next_batch
                yield batch

        if self.last_sync:
            yield CaseSyncPhoneBatch(
                self.global_state,
                self.domain,
                self.last_sync
            )


class CaseSyncBatch(object):
    """
    Object representing a batch of case updates to sync.
    """
    def __init__(self, global_state, domain, last_sync):
        self.global_state = global_state
        self.domain = domain
        self.last_sync = last_sync
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
        case_updates_to_sync = []
        for case in all_potential_to_sync:
            sync_update = CaseSyncUpdate(case, self.last_sync)
            if sync_update.required_updates:
                case_updates_to_sync.append(sync_update)

        return case_updates_to_sync


class CaseSyncPhoneBatch(CaseSyncBatch):
    """
    Batch of updates representing all cases that are on the phone
    but aren't part of the 'owned' cases of the user.
    """
    @property
    def case_updates_to_sync(self):
        other_case_ids_on_phone = set([
            case_id for case_id in self.last_sync.get_footprint_of_cases_on_phone()
            if case_id not in self.global_state.actual_relevant_cases_dict
        ])
        other_cases_on_phone = CommCareCase.view(
            "case/get_lite",
            keys=list(other_case_ids_on_phone)
        ).all()
        potential_to_sync = self._get_potential_cases(other_cases_on_phone)
        case_sync_updates = self._case_sync_updates(potential_to_sync)
        self.global_state.update_synced_cases(case_sync_updates)
        return case_sync_updates

    def __repr__(self):
        return "CaseSyncPhoneBatch()"


class CaseSyncCouchBatch(CaseSyncBatch):
    """
    Batch of case updates for cases 'owned' by the user.
    """
    def __init__(self, global_state, domain, last_sync, chunksize, startkey, startkey_docid=None):
        super(CaseSyncCouchBatch, self).__init__(global_state, domain, last_sync)
        self.chunksize = chunksize
        self.startkey = startkey
        self.startkey_docid = startkey_docid
        self.view_kwargs = {
            'startkey': startkey,
            'endkey': startkey,
            'limit': chunksize
        }
        if self.startkey_docid:
            self.view_kwargs['startkey_docid'] = self.startkey_docid
            self.view_kwargs['skip'] = 1

    @property
    def case_updates_to_sync(self):
        actual_owned_cases = self._actual_owned_cases()
        if not actual_owned_cases:
            return []

        self.global_state.update_owned_cases(actual_owned_cases)

        all_relevant_cases_dict = self._all_relevant_cases_dict(actual_owned_cases)
        actual_relevant_cases = self.global_state.update_relevant_cases(all_relevant_cases_dict.values())

        potential_to_sync = self._get_potential_cases(actual_relevant_cases)
        case_sync_updates = self._case_sync_updates(potential_to_sync)
        self.global_state.update_synced_cases(case_sync_updates)

        return case_sync_updates

    def _view_results(self):
        results = CommCareCase.get_db().view(
            "case/by_owner_lite",
            **self.view_kwargs
        )
        len_results = len(results)

        for result in results:
            yield result

        if len_results >= self.chunksize:
            self.next_batch = CaseSyncCouchBatch(
                self.global_state,
                self.domain,
                self.last_sync,
                self.chunksize,
                self.startkey,
                startkey_docid=result['id']
            )

    def _actual_owned_cases(self):
        def _case_domain_match(case):
            return not self.domain or self.domain == case.get('domain')

        return [
            CommCareCase.wrap(result['value']) for result in self._view_results()
            if _case_domain_match(result['value'])
        ]

    def _all_relevant_cases_dict(self, cases):
        return get_footprint(cases, domain=self.domain)

    def __repr__(self):
        return "CaseSyncCouchBatch(startkey={}, startkey_docid={}, chunksize={})".format(
            self.startkey,
            self.startkey_docid,
            self.chunksize
        )


def get_case_updates(user, last_sync):
    """
    Given a user, get the open/updated cases since the last sync
    operation.  This returns a CaseSyncOperation object containing
    various properties about cases that should sync.
    """
    return CaseSyncOperation(user, last_sync)

def filter_cases_modified_elsewhere_since_sync(cases, last_sync):
    # this function is pretty ugly and is heavily optimized to reduce the number
    # of queries to couch.
    if not last_sync:
        return cases
    else:
        case_ids = [case._id for case in cases]
        case_log_map = CommCareCase.get_db().view('phone/cases_to_sync_logs',
            keys=case_ids,
            reduce=False,
        )
        # incoming format is a list of objects that look like this:
        # {
        #   'value': '[log id]',
        #   'key': '[case id]',
        # }
        unique_combinations = set((row['key'], row['value']) for row in case_log_map)
        modification_dates = CommCareCase.get_db().view('phone/case_modification_status',
            keys=[list(combo) for combo in unique_combinations],
            reduce=True,
            group=True,
        )
        # we'll build a structure that looks like this for efficiency:
        # { case_id: [{'token': 'token value', 'date': 'date value'}, ...]}
        all_case_updates_by_sync_token = defaultdict(list)
        for row in modification_dates:
            # incoming format is a list of objects that look like this:
            # {
            #   'value': '2012-08-22T08:55:14Z', (most recent date updated)
            #   'key': ['[case id]', '[sync token id]']
            # }
            if row['value']:
                all_case_updates_by_sync_token[row['key'][0]].append(
                    {'token': row['key'][1], 'date': datetime.strptime(row['value'], '%Y-%m-%dT%H:%M:%SZ')}
                )

        def case_modified_elsewhere_since_sync(case):
            # NOTE: uses closures
            return any([row['date'] >= last_sync.date and row['token'] != last_sync._id
                        for row in all_case_updates_by_sync_token[case._id]])

        def relevant(case):
            return case_modified_elsewhere_since_sync(case) or not last_sync.phone_is_holding_case(case.get_id)

        return filter(relevant, cases)
