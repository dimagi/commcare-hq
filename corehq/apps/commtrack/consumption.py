from casexml.apps.stock import const
from casexml.apps.stock.models import DocDomainMapping, StockTransaction
from casexml.apps.stock.signals import update_stock_state_for_transaction
from corehq.apps.products.models import Product
from corehq.util.quickcache import quickcache


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
            ).order_by('-report__date', '-pk')
            if filtered_transactions:
                update_stock_state_for_transaction(filtered_transactions[0])


@quickcache(['domain'], timeout=30 * 60)
def should_exclude_invalid_periods(domain):
    """
    Whether the domain's consumption calculation should exclude invalid periods
    """
    from corehq.apps.commtrack.models import CommtrackConfig
    if domain:
        config = CommtrackConfig.for_domain(domain)
        if config:
            return config.consumption_config.exclude_invalid_periods
    return False
