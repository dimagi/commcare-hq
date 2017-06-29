from casexml.apps.phone.data_providers import FullResponseDataProvider
from casexml.apps.phone.data_providers.case.clean_owners import CleanOwnerCaseSyncOperation
from casexml.apps.phone.data_providers.case.livequery import do_livequery


class CasePayloadProvider(FullResponseDataProvider):
    """
    Full restore provider responsible for generating the case and stock payloads.
    """

    def get_response(self, restore_state):
        if restore_state.is_livequery:
            return do_livequery(self.timing_context, restore_state, self.async_task)
        sync_op = CleanOwnerCaseSyncOperation(self.timing_context, restore_state, self.async_task)
        return sync_op.get_payload()
