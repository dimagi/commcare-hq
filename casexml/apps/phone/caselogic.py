"""
Logic about chws phones and cases go here.
"""
from datetime import datetime
from casexml.apps.case.models import CommCareCase
from casexml.apps.case import const

def get_footprint(initial_case_list, strip_history=False):
    """
    Get's the flat list of the footprint of cases based on a starting list.
    Walks all the referenced indexes recursively.
    """
    
    def children(case):
        return [CommCareCase.get(index.referenced_id,
                                 strip_history=strip_history) \
                for index in case.indices]
    
    relevant_cases = {}
    queue = list(case for case in initial_case_list)
    while queue:
        case = queue.pop()
        if case.case_id not in relevant_cases:
            relevant_cases[case.case_id] = case
            queue.extend(children(case))
    return relevant_cases

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
        
        def case_modified_elsewhere_since_sync(case):
            # this function uses closures so can't be moved
            if not last_sync:
                return True
            else:
                case_actions = CommCareCase.get_db().view('case/actions_by_case', key=case._id).all()
                actions_sorted = sorted(case_actions, key=lambda x: x['value']['seq'])
                for action in actions_sorted:
                    server_date_string = action['value'].get('server_date', None)
                    server_date = datetime.strptime(server_date_string, '%Y-%m-%dT%H:%M:%SZ') \
                                    if server_date_string else None
                    sync_log_id = action['value'].get('sync_log_id', None)
                    if server_date and \
                       server_date >= last_sync.date and \
                       sync_log_id != last_sync.get_id:
                        return True
            
            # If we got down here, as a last check make sure the phone
            # is aware of the case. There are some corner cases where
            # this won't be true
            if not last_sync.phone_is_holding_case(case.get_id):
                return True
            
            # We're good.
            return False
        
        # the world to sync involves
        # Union(cases on the phone, footprint of those,  
        #       cases the server thinks are the phone's, footprint of those) 
        # intersected with:
        # (cases modified by someone else since the last sync)
        
        # TODO: clean this up. Basically everything is a set of cases,
        # but in order to do proper comparisons we use IDs so all of these
        # operations look much more complicated than they should be.

        self.actual_owned_cases = set(CommCareCase.view("case/by_owner_lite", keys=keys).all())
        self._all_relevant_cases = get_footprint(self.actual_owned_cases)
        
        def _to_case_id_set(cases):
            return set([c.case_id for c in cases])
        
        def _get_case(case_id):
            return self._all_relevant_cases[case_id] \
                if case_id in self._all_relevant_cases else CommCareCase.get(case_id)
            
        
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
        
        self.all_potential_to_sync = filter(case_modified_elsewhere_since_sync,
                                            list(self.all_potential_cases))
        
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

