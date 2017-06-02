"""Restore logic implementation aiming to minimize database queries
"""
from casexml.apps.phone.data_providers.case.load_testing import (
    get_xml_for_response,
)
from casexml.apps.phone.data_providers.case.stock import get_stock_payload
from casexml.apps.phone.data_providers.case.utils import (
    CaseStub,
    get_case_sync_updates,
)
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

def get_payload(timing_context, restore_state):
    """Get case sync restore response
    """
    case_accessor = CaseAccessors(restore_state.domain)

    # TODO maybe process cases in batches rather than loading all in memory at once
    # clean_owners.py does this, although not clear if due to memory constraints

    with timing_context("livequery"):
        with timing_context("get_open_cases_by_owners"):
            cases = case_accessor.get_open_cases_by_owners(restore_state.owner_ids)

        live_ids = next_ids = {case.case_id for case in cases}
        related_level = 0
        while next_ids:
            related_level += 1
            with timing_context("get_related_cases(level %s)" % related_level):
                related_cases = case_accessor.get_related_cases(next_ids, live_ids)
            if not related_cases:
                break
            next_ids = set()
            for case in related_cases:
                if case.case_id not in live_ids:
                    cases.append(case)
                    live_ids.add(case.case_id)
                    next_ids.add(case.case_id)

        # TODO? save updated sync logs (is this part of a restore? hopefully not)
        # TODO? tell phone to remove no-longer-relevant cases?

        with timing_context("compile_response"):
            response = compile_response(timing_context, cases, restore_state)

    return response


def compile_response(timing_context, cases, restore_state):
    response = restore_state.restore_class()

    with timing_context("get_commtrack_elements"):
        response.extend(get_commtrack_elements(cases, restore_state))

    with timing_context("get_case_sync_updates (%s cases)" % len(cases)):
        # TODO verify that clean_owners.py:process_case_batch does not change persistent state
        updates = get_case_sync_updates(
            restore_state.domain, cases, restore_state.last_sync_log)

    with timing_context("get_xml_for_response (%s updates)" % len(updates)):
        response.extend(item
            for update in updates
            for item in get_xml_for_response(update, restore_state)

    return response


def get_commtrack_elements(cases, restore_state):
    return get_stock_payload(
        restore_state.project,
        restore_state.stock_settings,
        [CaseStub(case.case_id, case.type) for case in cases],
    )
