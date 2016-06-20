from casexml.apps.phone.data_providers import FullResponseDataProvider
from casexml.apps.phone.data_providers.case.clean_owners import CleanOwnerCaseSyncOperation


class CasePayloadProvider(FullResponseDataProvider):
    """
    Full restore provider responsible for generating the case and stock payloads.
    """

    def get_response(self, restore_state, async_task=None):
        sync_op = CleanOwnerCaseSyncOperation(self.timing_context, restore_state, async_task)
        return sync_op.get_payload()
