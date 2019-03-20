from __future__ import absolute_import
from __future__ import unicode_literals
from django.db.models.signals import post_save

from casexml.apps.stock import const
from casexml.apps.stock.models import DocDomainMapping, StockTransaction
from casexml.apps.stock.signals import get_stock_state_for_transaction
from corehq.apps.products.models import Product
from corehq.util.context_managers import drop_connected_signals
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
            try:
                latest_transaction = StockTransaction.get_ordered_transactions_for_stock(
                    supply_point_id, const.SECTION_TYPE_STOCK, product._id
                )[0]
            except IndexError:
                pass
            else:
                state = get_stock_state_for_transaction(latest_transaction)
                daily_consumption = get_consumption_for_ledger(state)
                state.daily_consumption = daily_consumption
                with drop_connected_signals(post_save):
                    state.save()


def get_consumption_for_ledger(ledger):
    return get_consumption_for_ledger_json(ledger.to_json())


def get_consumption_for_ledger_json(ledger_json):
    from corehq.apps.domain.models import Domain
    from casexml.apps.stock.consumption import compute_daily_consumption
    from dimagi.utils.parsing import string_to_utc_datetime

    domain_name = ledger_json['domain']
    domain_obj = Domain.get_by_name(domain_name)
    if domain_obj and domain_obj.commtrack_settings:
        consumption_calc = domain_obj.commtrack_settings.get_consumption_config()
    else:
        consumption_calc = None
    daily_consumption = compute_daily_consumption(
        domain_name,
        ledger_json['case_id'],
        ledger_json['entry_id'],
        string_to_utc_datetime(ledger_json['last_modified']),
        'stock',
        consumption_calc
    )
    return daily_consumption


@quickcache(['domain'], timeout=30 * 60)
def should_exclude_invalid_periods(domain):
    """
    Whether the domain's consumption calculation should exclude invalid periods
    i.e. periods where the stock went up without a receipt being reported
    """
    from corehq.apps.commtrack.models import CommtrackConfig
    if domain:
        config = CommtrackConfig.for_domain(domain)
        if config:
            return config.consumption_config.exclude_invalid_periods
    return False
