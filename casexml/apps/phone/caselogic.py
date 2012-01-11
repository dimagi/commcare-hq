"""
Logic about chws phones and cases go here.
"""
from casexml.apps.case.models import CommCareCase
from casexml.apps.case import const

def required_updates(synclog, case):
    
    if case.closed:
        # if the case is closed, this means we must be trying 
        # to purge it from a phone which means there must
        # be a sync log
        assert(synclog is not None)
        return [const.CASE_ACTION_CLOSE] \
            if synclog.phone_has_case(case.get_id) \
            else []    
    
    else:
        ret = []
        if not synclog or not synclog.phone_has_case(case.get_id):
            ret.append(const.CASE_ACTION_CREATE)
                
        # always include an update 
        ret.append(const.CASE_ACTION_UPDATE)
        return ret
    
def get_footprint(initial_case_list):
    """
    Get's the flat list of the footprint of cases based on a starting list.
    Walks all the referenced indexes recursively.
    """
    def children(case):
        return [CommCareCase.get(index.referenced_id) \
                for index in case.indices]
    
    relevant_cases = set()
    queue = list(case for case in initial_case_list)
    while queue:
        case = queue.pop()
        if case.case_id not in relevant_cases:
            relevant_cases.add(case)
            queue.extend(children(case))
    return relevant_cases

    
def get_case_updates(user, last_sync):
    """
    Given a user, get the open/updated cases since the 
    last sync operation.  This returns tuples of phone_case objects, and flags
    that say whether or not they should be created.
    """
    try:
        keys = [[owner_id, False] for owner_id in user.get_owner_ids()]
    except AttributeError:
        keys = [[user.user_id, False]]
    
    def case_modified_elsewhere_since_sync(case):
        # this function uses closures so can't be moved
        if not last_sync:
            return True
        else:
            for action in case.actions:
                if action.server_date > last_sync.date and \
                   action.sync_log_id != last_sync.get_id:
                    return True
        return False
    
    to_return = []
    
    # the world to sync involves
    # Union(cases on the phone, footprint of those,  
    #       cases the server thinks are the phone's, footprint of those) 
    # intersected with:
    # (cases modified by someone else since the last sync)
    server_owned_cases = CommCareCase.view("case/by_owner", keys=keys,
                                           include_docs=True).all()
    server_relevant_cases = get_footprint(server_owned_cases)
    phone_relevant_cases = set([CommCareCase.get(case_id) for case_id \
                                in last_sync.get_footprint_of_cases_on_phone()]) \
                           if last_sync else set()
    
    all_potential_cases = server_relevant_cases | phone_relevant_cases
    
    all_potential_modified_elsewhere = filter(case_modified_elsewhere_since_sync, 
                                              list(all_potential_cases))
    # handle create/update of new material for the phone
    for case in all_potential_modified_elsewhere:
        operations = required_updates(last_sync, case)
        if operations:
            to_return.append((case, operations))

    return to_return


