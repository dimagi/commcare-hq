from __future__ import absolute_import, unicode_literals

from collections import defaultdict, namedtuple

from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors


def get_wrapped_ledger_values(domain, case_ids, section_id, entry_ids=None):
    if isinstance(case_ids, (list, tuple, set)):
        case_ids_list = list(case_ids)
    else:
        case_ids_list = [case_ids]
    return LedgerAccessors(domain).get_ledger_values_for_cases(case_ids_list, [section_id], entry_ids)


def products_with_ledgers(domain, case_ids, section_id, entry_ids=None):
    return {
        ledger.entry_id
        for ledger in get_wrapped_ledger_values(domain, case_ids, section_id, entry_ids)
    }


def get_aggregated_ledger_values(domain, case_ids, section_id, entry_ids=None):
    ledgers = get_wrapped_ledger_values(domain, case_ids, section_id, entry_ids)
    ret = defaultdict(lambda: 0)
    for ledger in ledgers:
        ret[ledger.entry_id] += ledger.balance

    row_class = namedtuple('AggregateLedgerValue', ['entry_id', 'balance'])
    return [
        row_class(entry_id, balance)
        for entry_id, balance in ret.items()
    ]
