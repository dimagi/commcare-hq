from casexml.apps.phone.data_providers import FullResponseDataProvider
from casexml.apps.phone.data_providers.case.clean_owners import CleanOwnerCaseSyncOperation
from casexml.apps.phone.data_providers.case.livequery import get_payload
from corehq.util.soft_assert import soft_assert


_livequery_assert = soft_assert(to='{}@{}'.format('dmiller', 'dimagi.com'))


class CasePayloadProvider(FullResponseDataProvider):
    """
    Full restore provider responsible for generating the case and stock payloads.
    """

    def get_response(self, restore_state):
        sync_op = CleanOwnerCaseSyncOperation(self.timing_context, restore_state, self.async_task)
        payload = sync_op.get_payload()
        if not self.async_task and should_do_livequery():
            lq_payload = get_payload(self.timing_context, restore_state)
            diff = compare_responses(payload, lq_payload)
            _livequery_assert(not diff, "livequery payload mismatch: {}".format(diff))
        return payload


# remove if/when livequery is no longer being compared
from datetime import datetime, timedelta
LIVEQUERY_INTERVAL = timedelta(minutes=5)

def should_do_livequery(next_check=[datetime.now() + LIVEQUERY_INTERVAL]):
    now = datetime.now()
    if next_check[0] > now:
        return False
    next_check[0] = now + LIVEQUERY_INTERVAL
    return True

def compare_responses(one, two):
    """Return a string diff of the two responses

    The returned value will evaluate to false if the given responses
    are equivalent.
    """
    # TODO implement comparison
    return ''
