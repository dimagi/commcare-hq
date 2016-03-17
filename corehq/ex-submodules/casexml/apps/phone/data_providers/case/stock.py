from collections import defaultdict
from casexml.apps.stock.consumption import compute_consumption_or_default
from casexml.apps.stock.utils import get_current_ledger_state
from dimagi.utils.parsing import json_format_datetime
from datetime import datetime
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS


def get_stock_payload(project, stock_settings, case_stub_list):
    if project and not project.commtrack_enabled:
        return

    from lxml.builder import ElementMaker
    E = ElementMaker(namespace=COMMTRACK_REPORT_XMLNS)

    def entry_xml(id, quantity):
        return E.entry(
            id=id,
            quantity=str(int(quantity)),
        )

    def state_to_xml(state):
        return entry_xml(state.product_id, state.stock_on_hand)

    def consumption_entry(case_id, product_id, section_id):
        consumption_value = compute_consumption_or_default(
            project.name,
            case_id,
            product_id,
            datetime.utcnow(),
            section_id,
            stock_settings.consumption_config
        )
        if consumption_value is not None:
            return entry_xml(product_id, consumption_value)

    case_ids = [case.case_id for case in case_stub_list]
    all_current_ledgers = get_current_ledger_state(case_ids)
    for commtrack_case_stub in case_stub_list:
        case_id = commtrack_case_stub.case_id
        current_ledgers = all_current_ledgers[case_id]

        section_product_map = defaultdict(lambda: [])
        section_timestamp_map = defaultdict(lambda: json_format_datetime(datetime.utcnow()))
        for section_id in sorted(current_ledgers.keys()):
            state_map = current_ledgers[section_id]
            sorted_product_ids = sorted(state_map.keys())
            stock_states = [state_map[p] for p in sorted_product_ids]
            as_of = json_format_datetime(max(txn.last_modified_date for txn in stock_states))
            section_product_map[section_id] = sorted_product_ids
            section_timestamp_map[section_id] = as_of
            yield E.balance(*(state_to_xml(e) for e in stock_states),
                            **{'entity-id': case_id, 'date': as_of, 'section-id': section_id})

        for section_id, consumption_section_id in stock_settings.section_to_consumption_types.items():

            if (section_id in current_ledgers or
                    stock_settings.force_consumption_case_filter(commtrack_case_stub)):

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
