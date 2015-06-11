from casexml.apps.phone.data_providers import LongRunningRestoreDataProvider
from casexml.apps.phone.data_providers.case.batched import get_case_payload_batched
from casexml.apps.phone.data_providers.case.clean_owners import get_case_payload


class CasePayloadProvider(LongRunningRestoreDataProvider):
    """
    Long running restore provider responsible for generating the case and stock payloads.
    """
    def get_response(self, restore_state):
        if restore_state.use_clean_restore:
            return get_case_payload(restore_state)
        else:
            return _batched_response(restore_state)


def _batched_response(restore_state):
    case_response, num_batches = get_case_payload_batched(
        restore_state=restore_state,
    )
    # keep track of the number of batches (if any) for comparison in unit tests
    restore_state.provider_log['num_case_batches'] = num_batches
    return case_response
