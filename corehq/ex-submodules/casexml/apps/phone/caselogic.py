"""
Logic about chws phones and cases go here.
"""
from collections import defaultdict
from datetime import datetime
import itertools
import logging
from casexml.apps.case.models import CommCareCase
from casexml.apps.case import const
from casexml.apps.case.xform import CaseDbCache


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
                          deleted_ok=True)

    def related(case_db, case):
        return [case_db.get(index.referenced_id) for index in (case.indices if search_up else case.reverse_indices)]

    relevant_cases = {}
    relevant_deleted_case_ids = []

    queue = list(case for case in initial_case_list)
    directly_referenced_indices = itertools.chain(*[[index.referenced_id for index in (case.indices if search_up else case.reverse_indices)]
                                                    for case in initial_case_list])
    case_db.populate(directly_referenced_indices)
    while queue:
        case = queue.pop()
        if case and case.case_id not in relevant_cases:
            relevant_cases[case.case_id] = case
            if case.doc_type == 'CommCareCase-Deleted':
                relevant_deleted_case_ids.append(case.case_id)
            queue.extend(related(case_db, case))

    if relevant_deleted_case_ids:
        logging.info('deleted cases included in footprint (restore): %s' % (
            ', '.join(relevant_deleted_case_ids)
        ))
    return relevant_cases


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

class CaseSyncOperation(object):
    """
    A record of a user's sync operation
    """
    
    def __init__(self, user, last_sync):
        try:
            keys = [[owner_id, False] for owner_id in user.get_owner_ids()]
        except AttributeError:
            keys = [[user.user_id, False]]

        def _user_case_domain_match(case):
            if user.domain:
                return user.domain == case.domain
            return True

        # the world to sync involves
        # Union(cases on the phone, footprint of those,  
        #       cases the server thinks are the phone's, footprint of those) 
        # intersected with:
        # (cases modified by someone else since the last sync)
        
        # TODO: clean this up. Basically everything is a set of cases,
        # but in order to do proper comparisons we use IDs so all of these
        # operations look much more complicated than they should be.

        self.actual_owned_cases = set(filter(_user_case_domain_match,
                                             CommCareCase.view("case/by_owner_lite", keys=keys).all()))
        self._all_relevant_cases = get_footprint(self.actual_owned_cases, domain=user.domain)
        
        def _to_case_id_set(cases):
            return set([c.case_id for c in cases])
        
        def _get_case(case_id):
            if case_id in self._all_relevant_cases:
                return self._all_relevant_cases[case_id]
            else:
                case = CommCareCase.get_with_rebuild(case_id)
                self._all_relevant_cases[case_id] = case
                return case

        self.actual_relevant_cases = set(self._all_relevant_cases.values())
        
        
        self.actual_extended_cases = set([_get_case(case_id) for case_id in \
                                          _to_case_id_set(self.actual_relevant_cases) - \
                                          _to_case_id_set(self.actual_owned_cases)])
        
        self.phone_relevant_cases = set([_get_case(case_id) for case_id \
                                         in last_sync.get_footprint_of_cases_on_phone()]) \
                                    if last_sync else set()
        
        self.all_potential_cases = set([_get_case(case_id) for case_id in \
                                        _to_case_id_set(self.actual_relevant_cases) | \
                                        _to_case_id_set(self.phone_relevant_cases)])
        
        self.all_potential_to_sync = filter_cases_modified_elsewhere_since_sync(
            list(self.all_potential_cases), last_sync)
        
        # this is messy but forces uniqueness at the case_id level, without
        # having to reload all the cases from the DB
        self.all_potential_to_sync_dict = dict((case.get_id, case) \
                                               for case in self.all_potential_to_sync)
        
        self.actual_cases_to_sync = []
        for _, case in self.all_potential_to_sync_dict.items():
            sync_update = CaseSyncUpdate(case, last_sync)
            if sync_update.required_updates:
                self.actual_cases_to_sync.append(sync_update)

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
        # { case_id: [{'token': '[token value', 'date': '[date value]'}, ...]}
        all_case_updates_by_sync_token = defaultdict(lambda: [])
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
