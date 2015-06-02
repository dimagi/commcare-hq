from django.conf import settings
from casexml.apps.phone.data_providers import LongRunningRestoreDataProvider
from casexml.apps.phone.data_providers.case.batched import get_case_payload_batched
from casexml.apps.phone.data_providers.case.clean_owners import get_case_payload
from corehq.toggles import OWNERSHIP_CLEANLINESS_RESTORE


class CasePayloadProvider(LongRunningRestoreDataProvider):
    """
    Long running restore provider responsible for generating the case and stock payloads.
    """
    def get_response(self, restore_state):
        if should_use_clean_restore(restore_state.domain):
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


def should_use_clean_restore(domain):
    if settings.UNIT_TESTING:
        override = getattr(
            settings, 'TESTS_SHOULD_USE_CLEAN_RESTORE', None)
        if override is not None:
            return override
    return OWNERSHIP_CLEANLINESS_RESTORE.enabled(domain)
