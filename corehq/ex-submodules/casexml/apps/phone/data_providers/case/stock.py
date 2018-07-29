from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
from datetime import datetime

from corehq import toggles
from corehq.form_processor.exceptions import LedgerValueNotFound
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from memoized import memoized
from dimagi.utils.parsing import json_format_datetime

from casexml.apps.stock.consumption import compute_default_monthly_consumption, \
    ConsumptionConfiguration
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS


def get_stock_payload(project, stock_settings, case_stub_list):
    uses_ledgers = project.commtrack_enabled or toggles.NON_COMMTRACK_LEDGERS.enabled(project.name)
    if project and not uses_ledgers:
        return

    generator = StockPayloadGenerator(project.name, stock_settings, case_stub_list)
    for section in generator.yield_sections():
        yield section


class StockPayloadGenerator(object):
    def __init__(self, domain_name, stock_settings, case_stub_list):
        self.domain_name = domain_name
        self.stock_settings = stock_settings
        self.case_stub_list = case_stub_list

        from lxml.builder import ElementMaker
        self.elem_maker = ElementMaker(namespace=COMMTRACK_REPORT_XMLNS)

    def yield_sections(self):
        case_ids = [case.case_id for case in self.case_stub_list]
        all_current_ledgers = LedgerAccessors(self.domain_name).get_current_ledger_state(case_ids)
        for case_stub in self.case_stub_list:
            case_id = case_stub.case_id
            case_ledgers = all_current_ledgers[case_id]

            section_timestamp_map = defaultdict(lambda: json_format_datetime(datetime.utcnow()))
            for section_id in sorted(case_ledgers.keys()):
                state_map = case_ledgers[section_id]
                stock_states = sorted(list(state_map.values()), key=lambda s: s.product_id)
                as_of = json_format_datetime(max(txn.last_modified_date for txn in stock_states))
                section_timestamp_map[section_id] = as_of
                yield self.elem_maker.balance(
                    *(self._state_to_xml(e) for e in stock_states),
                    **{'entity-id': case_id, 'date': as_of, 'section-id': section_id}
                )

            if self.stock_settings.sync_consumption_ledger:
                for section in self._consumption_sections(case_stub, case_ledgers, section_timestamp_map):
                    yield section

    def _consumption_sections(self, case_stub, case_ledgers, section_timestamp_map):
        case_id = case_stub.case_id
        for section_id, consumption_section_id in self.stock_settings.section_to_consumption_types.items():
            if section_id in case_ledgers or self.stock_settings.force_consumption_case_filter(case_stub):

                consumption_entries = []
                current_section_sate = case_ledgers.get(section_id, {})
                if self.stock_settings.default_product_list:
                    for product_id in self.stock_settings.default_product_list:
                        state = current_section_sate.get(product_id, None)
                        if not state:
                            try:
                                state = LedgerAccessors(self.domain_name).get_ledger_value(
                                    case_id, section_id, product_id
                                )
                            except LedgerValueNotFound:
                                pass

                        consumption_entries.append(
                            self._consumption_entry(case_id, product_id, state)
                        )
                else:
                    for product_id in sorted(current_section_sate.keys()):
                        state = current_section_sate[product_id]
                        consumption_entries.append(
                            self._consumption_entry(case_id, product_id, state)
                        )

                consumption_entries = [e for e in consumption_entries if e is not None]
                if consumption_entries:
                    yield self.elem_maker.balance(
                        *consumption_entries,
                        **{
                            'entity-id': case_id,
                            'date': section_timestamp_map[section_id],
                            'section-id': consumption_section_id,
                        }
                    )

    def _entry_xml(self, id, quantity):
        return self.elem_maker.entry(
            id=id,
            quantity=str(int(quantity)),
        )

    def _state_to_xml(self, state):
        return self._entry_xml(state.product_id, state.stock_on_hand)

    def _consumption_entry(self, case_id, product_id, state):
        if state and state.daily_consumption is not None:
            return self._entry_xml(state.product_id, state.daily_consumption)

        return self._default_consumption_entry(case_id, product_id)

    @memoized
    def _default_consumption_entry(self, case_id, product_id):
        configuration = self.stock_settings.consumption_config or ConsumptionConfiguration()
        default_value = compute_default_monthly_consumption(
            case_id,
            product_id,
            configuration,
        )
        if default_value is not None:
            return self._entry_xml(product_id, default_value)
