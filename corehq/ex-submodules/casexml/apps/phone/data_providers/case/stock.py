from collections import defaultdict
from casexml.apps.stock.consumption import compute_consumption_or_default, compute_default_monthly_consumption, \
    ConsumptionConfiguration
from casexml.apps.stock.utils import get_current_ledger_state
from corehq.form_processor.exceptions import LedgerValueNotFound
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from dimagi.utils.decorators.memoized import memoized
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

    def consumption_entry(case_id, product_id, state):
        if state and state.daily_consumption is not None:
            return entry_xml(state.product_id, state.daily_consumption)

        return default_consumption_entry(case_id, product_id)

    @memoized
    def default_consumption_entry(case_id, product_id):
        configuration = stock_settings.consumption_config or ConsumptionConfiguration()
        default_value = compute_default_monthly_consumption(
            case_id,
            product_id,
            configuration,
        )
        if default_value is not None:
            return entry_xml(product_id, default_value)

    case_ids = [case.case_id for case in case_stub_list]
    all_current_ledgers = LedgerAccessors(project.name).get_current_ledger_state(case_ids)
    for commtrack_case_stub in case_stub_list:
        case_id = commtrack_case_stub.case_id
        current_ledgers = all_current_ledgers[case_id]

        section_timestamp_map = defaultdict(lambda: json_format_datetime(datetime.utcnow()))
        for section_id in sorted(current_ledgers.keys()):
            state_map = current_ledgers[section_id]
            sorted_product_ids = sorted(state_map.keys())
            stock_states = [state_map[p] for p in sorted_product_ids]
            as_of = json_format_datetime(max(txn.last_modified_date for txn in stock_states))
            section_timestamp_map[section_id] = as_of
            yield E.balance(*(state_to_xml(e) for e in stock_states),
                            **{'entity-id': case_id, 'date': as_of, 'section-id': section_id})

        for section_id, consumption_section_id in stock_settings.section_to_consumption_types.items():

            if (section_id in current_ledgers or
                    stock_settings.force_consumption_case_filter(commtrack_case_stub)):

                consumption_entries = []
                current_section_sate = current_ledgers.get(section_id, {})
                if stock_settings.default_product_list:
                    for product_id in stock_settings.default_product_list:
                        state = current_section_sate.get(product_id, None)
                        if not state:
                            try:
                                state = LedgerAccessors(project.name).get_ledger_value(
                                    case_id, section_id, product_id
                                )
                            except LedgerValueNotFound:
                                pass

                        consumption_entries.append(
                            consumption_entry(case_id, product_id, state)
                        )
                else:
                    for product_id in sorted(current_section_sate.keys()):
                        state = current_section_sate[product_id]
                        consumption_entries.append(
                            consumption_entry(case_id, product_id, state)
                        )

                if consumption_entries:
                    yield E.balance(
                        *consumption_entries,
                        **{
                            'entity-id': case_id,
                            'date': section_timestamp_map[section_id],
                            'section-id': consumption_section_id,
                        }
                    )
