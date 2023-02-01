from casexml.apps.phone.data_providers import AsyncDataProvider
from casexml.apps.phone.data_providers.case.livequery import do_livequery


class CasePayloadProvider(AsyncDataProvider):
    """
    Async provider responsible for generating the case and stock payloads.
    """

    def extend_response(self, restore_state, response):
        do_livequery(
            self.timing_context,
            restore_state,
            response,
            self.async_task,
        )
