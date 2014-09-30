from datetime import datetime
from corehq.apps.commtrack.models import SupplyPointCase
from custom.ilsgateway.models import SupplyPointStatus, ILSGatewayConfig
from dimagi.utils.dates import get_business_day_of_month_before
from corehq.apps.domain.models import Domain
from django.db.models.aggregates import Max

GROUPS = ('A', 'B', 'C')


def get_groups(groups):
    if isinstance(groups, list):
        return groups
    elif isinstance(groups, str):
        return groups.split(',')
    else:
        return None


def get_current_group():
    month = datetime.utcnow().month
    return GROUPS[(month+2) % 3]


def send_for_all_domains(date, fn, **kwargs):
    for domain in ILSGatewayConfig.get_all_enabled_domains():
        fn(domain, date, **kwargs)


def send_for_day(date, cutoff, f, **kwargs):
    now = datetime.utcnow()
    date = get_business_day_of_month_before(now.year, now.month, date)
    cutoff = get_business_day_of_month_before(now.year, now.month, cutoff)
    if now.day == date.day:
        send_for_all_domains(cutoff, f, **kwargs)


def supply_points_with_latest_status_by_datespan(sps, status_type, status_value, datespan):
    """
    This very similar method is used by the reminders.
    """
    ids = [sp._id for sp in sps]
    inner = SupplyPointStatus.objects.filter(supply_point__in=ids,
                                             status_type=status_type,
                                             status_date__gte=datespan.startdate,
                                             status_date__lte=datespan.enddate).annotate(pk=Max('id'))
    ids = SupplyPointStatus.objects.filter(id__in=inner.values('pk').query,
                                           status_type=status_type,
                                           status_value=status_value).distinct().values_list("supply_point", flat=True)
    return [SupplyPointCase.get(id) for id in ids]