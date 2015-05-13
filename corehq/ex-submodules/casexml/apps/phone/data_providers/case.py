from casexml.apps.phone.data_providers import LongRunningRestoreDataProvider


class CasePayloadProvider(LongRunningRestoreDataProvider):
    """
    Long running restore provider responsible for generating the case and stock payloads.
    """
    def get_response(self, restore_state):
        # todo: need to split these out more
        from casexml.apps.phone.restore import get_case_payload_batched, StockSettings

        if restore_state.domain and restore_state.domain.commtrack_settings:
            stock_settings = restore_state.domain.commtrack_settings.get_ota_restore_settings()
        else:
            stock_settings = StockSettings()

        case_response, num_batches = get_case_payload_batched(
            domain=restore_state.domain,
            stock_settings=stock_settings,
            version=restore_state.params.version,
            user=restore_state.user,
            last_synclog=restore_state.last_sync_log,
            new_synclog=restore_state.current_sync_log,
        )
        # keep track of the number of batches (if any) for comparison in unit tests
        restore_state.provider_log['num_case_batches'] = num_batches
        return case_response


