from casexml.apps.phone.data_providers import LongRunningRestoreDataProvider
from casexml.apps.phone.data_providers.case.batched import get_case_payload_batched


class CasePayloadProvider(LongRunningRestoreDataProvider):
    """
    Long running restore provider responsible for generating the case and stock payloads.
    """
    def get_response(self, restore_state):
        # todo: need to split these out more
        from casexml.apps.phone.restore import StockSettings

        if restore_state.domain and restore_state.domain.commtrack_settings:
            stock_settings = restore_state.domain.commtrack_settings.get_ota_restore_settings()
        else:
            stock_settings = StockSettings()

        case_response, num_batches = get_case_payload_batched(
            restore_state=restore_state,
            stock_settings=stock_settings,
        )
        # keep track of the number of batches (if any) for comparison in unit tests
        restore_state.provider_log['num_case_batches'] = num_batches
        return case_response
