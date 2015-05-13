from collections import defaultdict
from copy import deepcopy
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.caselogic import CaseSyncUpdate, BatchedCaseSyncOperation
from casexml.apps.phone.data_providers import LongRunningRestoreDataProvider
from casexml.apps.stock.consumption import compute_consumption_or_default
from casexml.apps.stock.utils import get_current_ledger_transactions_multi
from corehq.toggles import ENABLE_LOADTEST_USERS
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.couch.database import get_safe_write_kwargs
from casexml.apps.phone import xml
from datetime import datetime
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS


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


def get_case_payload_batched(restore_state, stock_settings):
    response = restore_state.restore_class()

    sync_operation = BatchedCaseSyncOperation(restore_state)
    factor = _get_loadtest_factor(restore_state.domain, restore_state.user)
    for update in sync_operation.get_all_case_updates():
        current_count = 0
        original_update = update
        while current_count < factor:
            element = xml.get_case_element(update.case, update.required_updates, restore_state.version)
            response.append(element)
            current_count += 1
            if current_count < factor:
                update = _transform_loadtest_update(original_update, current_count)

    sync_state = sync_operation.global_state
    restore_state.current_sync_log.cases_on_phone = sync_state.actual_owned_cases
    restore_state.current_sync_log.dependent_cases_on_phone = sync_state.actual_extended_cases
    restore_state.current_sync_log.save(**get_safe_write_kwargs())

    # commtrack balance sections
    commtrack_elements = get_stock_payload(restore_state.domain, stock_settings, sync_state.all_synced_cases)
    response.extend(commtrack_elements)

    return response, sync_operation.batch_count


def _get_loadtest_factor(domain, user):
    """
    Gets the loadtest factor for a domain and user. Is always 1 unless
    both the toggle is enabled for the domain, and the user has a non-zero,
    non-null factor set.
    """
    if domain and ENABLE_LOADTEST_USERS.enabled(domain.name):
        return getattr(user, 'loadtest_factor', 1) or 1
    return 1


def _transform_loadtest_update(update, factor):
    """
    Returns a new CaseSyncUpdate object (from an existing one) with all the
    case IDs and names mapped to have the factor appended.
    """
    def _map_id(id, count):
        return '{}-{}'.format(id, count)
    case = CommCareCase.wrap(deepcopy(update.case._doc))
    case._id = _map_id(case._id, factor)
    for index in case.indices:
        index.referenced_id = _map_id(index.referenced_id, factor)
    case.name = '{} ({})'.format(case.name, factor)
    return CaseSyncUpdate(case, update.sync_token, required_updates=update.required_updates)


def get_stock_payload(domain, stock_settings, case_state_list):
    if domain and not domain.commtrack_enabled:
        return

    from lxml.builder import ElementMaker
    E = ElementMaker(namespace=COMMTRACK_REPORT_XMLNS)

    def entry_xml(id, quantity):
        return E.entry(
            id=id,
            quantity=str(int(quantity)),
        )

    def transaction_to_xml(trans):
        return entry_xml(trans.product_id, trans.stock_on_hand)

    def consumption_entry(case_id, product_id, section_id):
        consumption_value = compute_consumption_or_default(
            case_id,
            product_id,
            datetime.utcnow(),
            section_id,
            stock_settings.consumption_config
        )
        if consumption_value is not None:
            return entry_xml(product_id, consumption_value)

    case_ids = [case.case_id for case in case_state_list]
    all_current_ledgers = get_current_ledger_transactions_multi(case_ids)
    for commtrack_case in case_state_list:
        case_id = commtrack_case.case_id
        current_ledgers = all_current_ledgers[case_id]

        section_product_map = defaultdict(lambda: [])
        section_timestamp_map = defaultdict(lambda: json_format_datetime(datetime.utcnow()))
        for section_id in sorted(current_ledgers.keys()):
            transactions_map = current_ledgers[section_id]
            sorted_product_ids = sorted(transactions_map.keys())
            transactions = [transactions_map[p] for p in sorted_product_ids]
            as_of = json_format_datetime(max(txn.report.date for txn in transactions))
            section_product_map[section_id] = sorted_product_ids
            section_timestamp_map[section_id] = as_of
            yield E.balance(*(transaction_to_xml(e) for e in transactions),
                            **{'entity-id': case_id, 'date': as_of, 'section-id': section_id})

        for section_id, consumption_section_id in stock_settings.section_to_consumption_types.items():

            if (section_id in current_ledgers or
                    stock_settings.force_consumption_case_filter(commtrack_case)):

                consumption_product_ids = stock_settings.default_product_list \
                    if stock_settings.default_product_list \
                    else section_product_map[section_id]

                consumption_entries = filter(lambda e: e is not None, [
                    consumption_entry(case_id, p, section_id)
                    for p in consumption_product_ids
                ])

                if consumption_entries:
                    yield E.balance(
                        *consumption_entries,
                        **{
                            'entity-id': case_id,
                            'date': section_timestamp_map[section_id],
                            'section-id': consumption_section_id,
                        }
                    )
