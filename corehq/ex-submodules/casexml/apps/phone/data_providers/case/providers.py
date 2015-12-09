from casexml.apps.phone.data_providers import LongRunningRestoreDataProvider
from casexml.apps.phone.data_providers.case.clean_owners import get_case_payload


class CasePayloadProvider(LongRunningRestoreDataProvider):
    """
    Long running restore provider responsible for generating the case and stock payloads.
    """
    def get_response(self, restore_state):
        return get_case_payload(restore_state)
