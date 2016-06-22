from casexml.apps.phone.data_providers import LongRunningRestoreDataProvider
from casexml.apps.phone.data_providers.case.clean_owners import CleanOwnerCaseSyncOperation


class CasePayloadProvider(LongRunningRestoreDataProvider):
    """
    Long running restore provider responsible for generating the case and stock payloads.
    """

    def get_response(self, restore_state):
        sync_op = CleanOwnerCaseSyncOperation(self.timing_context, restore_state)
        return sync_op.get_payload()
