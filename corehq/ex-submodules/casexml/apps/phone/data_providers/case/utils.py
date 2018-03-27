from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from casexml.apps.case import const


# stub class used by commtrack config to check case types for consumption payload
CaseStub = namedtuple('CaseStub', ['case_id', 'type'])


class CaseSyncUpdate(object):
    """
    The record of how a case should sync
    """

    def __init__(self, case, sync_token, required_updates=None):
        self.case = case
        self.sync_token = sync_token
        # cache this property since computing it can be expensive
        self.required_updates = required_updates if required_updates is not None else self._get_required_updates()

    def _get_required_updates(self):
        """
        Returns a list of the required updates for this case/token
        pairing. Should be a list of actions like [create, update, close]
        """
        ret = []
        if not self.sync_token or not self.sync_token.phone_is_holding_case(self.case.case_id):
            ret.append(const.CASE_ACTION_CREATE)
        # always include an update
        ret.append(const.CASE_ACTION_UPDATE)
        if self.case.closed:
            ret.append(const.CASE_ACTION_CLOSE)
        return ret


def get_case_sync_updates(domain, cases, last_sync_log):
    """
    Given a domain, list of cases, and sync log representing the last
    sync, return a list of CaseSyncUpdate objects that should be applied
    to the next sync.
    """
    case_updates_to_sync = []

    def _approximate_domain_match(case):
        # if both objects have a domain then make sure they're the same, but if
        # either is empty then just assume it's a match (this is just for legacy tests)
        return domain == case.domain if domain and case.domain else True

    for case in cases:
        sync_update = CaseSyncUpdate(case, last_sync_log)
        if sync_update.required_updates and _approximate_domain_match(case):
            case_updates_to_sync.append(sync_update)

    return case_updates_to_sync
