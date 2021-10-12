from corehq.util.quickcache import quickcache


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
        if config and hasattr(config, 'consumptionconfig'):
            return config.consumptionconfig.exclude_invalid_periods
    return False
