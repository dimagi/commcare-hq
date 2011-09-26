"""
Logic about chws phones and cases go here.
"""
from casexml.apps.case.models import CommCareCase
import logging

def case_previously_synced(case_id, last_sync):
    if not last_sync: return False
    return case_id in last_sync.get_synced_case_ids()
    
    
def get_open_cases_to_send(user, last_sync):
    """
    Given a user, get the open/updated cases since the 
    last sync operation.  This returns tuples of phone_case objects, and flags 
    that say whether or not they should be created.
    """ 
    to_return = []
    case_ids = []
    cases = CommCareCase.view("case/by_user", key=[user.user_id, False], reduce=False,
                              include_docs=True).all()
    for case in cases:
        # keep a running list of case ids sent down because the phone doesn't
        # deal well with duplicates.  There shouldn't be duplicates, but they
        # can come up with bugs, so arbitrarily only send down the first case
        # if there are any duplicates
        if case.case_id in case_ids:
            logging.error("Found a duplicate case for %s. Will not be sent to phone." % case.case_id)
        else:
            case_ids.append(case.case_id)
            previously_synced = case_previously_synced(case.case_id, last_sync)
            to_return.append((case, not previously_synced))
    return to_return


