from casexml.apps.phone.data_providers import FullResponseDataProvider
from casexml.apps.phone.data_providers.case.clean_owners import CleanOwnerCaseSyncOperation
from casexml.apps.phone.data_providers.case.livequery import get_payload


class CasePayloadProvider(FullResponseDataProvider):
    """
    Full restore provider responsible for generating the case and stock payloads.
    """

    def get_response(self, restore_state):
        if not self.async_task and restore_state.do_livequery:
            return get_payload(self.timing_context, restore_state)
        sync_op = CleanOwnerCaseSyncOperation(self.timing_context, restore_state, self.async_task)
        return sync_op.get_payload()
