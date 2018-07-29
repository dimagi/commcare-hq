from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.phone.data_providers import AsyncDataProvider
from casexml.apps.phone.data_providers.case.clean_owners import CleanOwnerCaseSyncOperation
from casexml.apps.phone.data_providers.case.livequery import do_livequery


class CasePayloadProvider(AsyncDataProvider):
    """
    Async provider responsible for generating the case and stock payloads.
    """

    def extend_response(self, restore_state, response):
        if restore_state.is_livequery:
            do_livequery(
                self.timing_context,
                restore_state,
                response,
                self.async_task,
            )
        else:
            CleanOwnerCaseSyncOperation(
                self.timing_context,
                restore_state,
                self.async_task,
            ).extend_response(response)
