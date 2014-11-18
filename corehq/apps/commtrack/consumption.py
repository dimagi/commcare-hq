from casexml.apps.stock import const
from casexml.apps.stock.models import DocDomainMapping, StockTransaction
from corehq.apps.commtrack.models import update_stock_state_for_transaction
from corehq.apps.products.models import Product


def recalculate_domain_consumption(domain):
    """
    Given a domain, recalculate all saved consumption settings in that domain.
    """
    # note: might get slow as this gets huge
    found_doc_ids = DocDomainMapping.objects.filter(
        domain_name=domain,
        doc_type='CommCareCase',
    ).values_list('doc_id', flat=True)
    products = Product.by_domain(domain)
    for supply_point_id in found_doc_ids:
        for product in products:
            filtered_transactions = StockTransaction.objects.filter(
                case_id=supply_point_id,
                product_id=product._id,
                section_id=const.SECTION_TYPE_STOCK,
            ).order_by('-report__date')
            if filtered_transactions:
                update_stock_state_for_transaction(filtered_transactions[0])
