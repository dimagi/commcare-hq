from datetime import datetime
from dimagi.utils.dates import get_business_day_of_month_before
from corehq.apps.domain.models import Domain

GROUPS = ('A', 'B', 'C')

def get_current_group():
    month = datetime.utcnow().month
    return GROUPS[(month+2) % 3]


def send_for_all_domains(date, fn, **kwargs):
    for domain in Domain.get_all():
        #TODO Merge with ILSGateway integration?
        #ilsgateway_config = ILSGatewayConfig.for_domain(domain.name)
        #if ilsgateway_config and ilsgateway_config.enabled:
        fn(domain.name, date, **kwargs)


def send_for_day(date, cutoff, f, **kwargs):
    print date, cutoff, f, kwargs
    now = datetime.utcnow()
    date = get_business_day_of_month_before(now.year, now.month, date)
    cutoff = get_business_day_of_month_before(now.year, now.month, cutoff)
    if now.day == date.day:
        send_for_all_domains(cutoff, f, **kwargs)