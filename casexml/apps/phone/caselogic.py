"""
Logic about chws phones and cases go here.
"""
from casexml.apps.case.models import CommCareCase
from datetime import datetime
import logging
from dimagi.utils.dates import utcnow_sans_milliseconds
from casexml.apps.case import const

def required_updates(synclog, case):
    ret = []
    # only allowed to call this method with a valid synclog
    assert(synclog is not None)
    
    # TODO: this method needs a complete rewrite.
    raise NotImplementedError("This is broken!")

    if case.get_server_modified_date() >= synclog.date:
        # only do any updates if the case has been touched since
        # the last time we synced
        if case.get_id not in synclog.get_all_cases_seen():
            # we've never seen it so we need a create block
            ret.append(const.CASE_ACTION_CREATE)
        # always include an update if it's been modified
        ret.append(const.CASE_ACTION_UPDATE)
        
        # closed intentionally not put in - closed cases are 
        # handled differently via the purge workflow
    return ret
    
def get_case_updates(user, last_sync):
    """
    Given a user, get the open/updated cases since the 
    last sync operation.  This returns tuples of phone_case objects, and flags
    that say whether or not they should be created.
    """
    try:
        keys = [[owner_id, False] for owner_id in user.get_owner_ids()]
    except AttributeError:
        keys = [[user.user_id, False],]
    
    to_return = []
    # keep a running list of case ids sent down because the phone doesn't
    # deal well with duplicates.  There shouldn't be duplicates, but they
    # can come up with bugs, so arbitrarily only send down the first case
    # if there are any duplicates
    
    case_ids = set()

    cases = CommCareCase.view("case/by_owner", keys=keys,
                              include_docs=True).all()

    # handle create/update of new material for the phone
    for case in cases:
        if case.case_id in case_ids:
            logging.error("Found a duplicate case for %s. Will not be sent to phone." % case.case_id)
        else:
            # the no-sync-token use case is really straightforward so special case it
            case_ids.add(case.case_id)
            if not last_sync:
                to_return.append((case, [const.CASE_ACTION_CREATE, const.CASE_ACTION_UPDATE]))
            else:
                operations = required_updates(last_sync, case)
                if operations:
                    to_return.append((case, operations))
    
    # handle purging of existing cases on phone
    if last_sync:
        # any currently open case that is no longer relevant 
        # (absent from sync list) should be purged.
        relevant_ids = set(c.get_id for c in cases)
        current_list = last_sync.get_open_cases_on_phone()
        to_purge = current_list - relevant_ids
        to_return.extend((CommCareCase.get(id), [const.CASE_ACTION_PURGE]) for id in to_purge)
        
    return to_return


