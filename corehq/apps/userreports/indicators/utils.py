from collections import defaultdict

from corehq.apps.products.models import SQLProduct
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors


def get_values_by_product(domain, case_id, ledger_section, product_codes):
    ledgers = LedgerAccessors(domain).get_ledger_values_for_case(case_id)

    products = SQLProduct.objects.filter(
        domain=domain, code__in=product_codes
    ).values('product_id', 'code')

    entry_id_to_code = {
        product['product_id']: product['code']
        for product in products
    }

    ledger_values = defaultdict(lambda: 0)
    for ledger in ledgers:
        if ledger.section_id == ledger_section and ledger.entry_id in entry_id_to_code:
            product_code = entry_id_to_code[ledger.entry_id]
            ledger_values[product_code] = ledger.stock_on_hand

    return ledger_values
