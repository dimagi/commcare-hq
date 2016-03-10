from datetime import datetime
from decimal import Decimal
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import LocationType, Location, SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.util.translation import localize
from custom.ilsgateway.models import SupplyPointStatus, ILSGatewayConfig, GroupSummary, SupplyPointStatusTypes, \
    DeliveryGroups
from dimagi.utils.dates import get_business_day_of_month_before
from django.db.models.aggregates import Max

GROUPS = ('A', 'B', 'C')


def get_next_meta_url(has_next, meta, next_url):
    if not meta.get('next', False):
        has_next = False
    else:
        next_url = meta['next'].split('?')[1]
    return has_next, next_url


def get_current_group():
    month = datetime.utcnow().month
    return GROUPS[(month + 2) % 3]


def send_for_all_domains(date, reminder_class, **kwargs):
    for domain in ILSGatewayConfig.get_all_enabled_domains():
        reminder_class(domain=domain, date=date, **kwargs).send()


def send_for_day(date, cutoff, reminder_class, **kwargs):
    now = datetime.utcnow()
    date = get_business_day_of_month_before(now.year, now.month, date)
    cutoff = get_business_day_of_month_before(now.year, now.month, cutoff)
    if now.day == date.day:
        send_for_all_domains(cutoff, reminder_class, **kwargs)


def supply_points_with_latest_status_by_datespan(locations, status_type, status_value, datespan):
    """
    This very similar method is used by the reminders.
    """
    ids = [loc.location_id for loc in locations]
    inner = SupplyPointStatus.objects.filter(location_id__in=ids,
                                             status_type=status_type,
                                             status_date__gte=datespan.startdate,
                                             status_date__lte=datespan.enddate).annotate(pk=Max('id'))
    ids = SupplyPointStatus.objects.filter(
        id__in=inner.values('pk').query,
        status_type=status_type,
        status_value=status_value).distinct().values_list("location_id", flat=True)
    return [SupplyPointCase.get(id) for id in ids]


def send_translated_message(user, message, **kwargs):
    verified_number = user.get_verified_number()
    if not verified_number:
        return False
    with localize(user.get_language_code()):
        send_sms_to_verified_number(verified_number, message % kwargs)
        return True


def make_loc(code, name, domain, type, metadata=None, parent=None):
    name = name or code
    LocationType.objects.get(domain=domain, name=type)
    loc = Location(site_code=code, name=name, domain=domain, location_type=type, parent=parent)
    loc.metadata = metadata or {}
    loc.save()
    return loc


def create_stock_report(location, products_quantities, date=datetime.utcnow()):
    sql_location = location.sql_location
    report = StockReport.objects.create(
        form_id='test-form-id',
        domain=sql_location.domain,
        type='balance',
        date=date
    )
    for product_code, quantity in products_quantities.iteritems():
        StockTransaction(
            stock_on_hand=Decimal(quantity),
            report=report,
            type='stockonhand',
            section_id='stock',
            case_id=sql_location.supply_point_id,
            product_id=SQLProduct.objects.get(domain=sql_location.domain, code=product_code).product_id
        ).save()


def last_location_group(location):
    try:
        gs = GroupSummary.objects.filter(
            total=1, org_summary__location_id=location.get_id, title=SupplyPointStatusTypes.DELIVERY_FACILITY
        ).latest('org_summary__date')
    except GroupSummary.DoesNotExist:
        return

    delivery_groups = DeliveryGroups(gs.org_summary.date.month)
    return delivery_groups.current_delivering_group()


def get_sql_locations_by_domain_and_group(domain, group):
    for sql_location in SQLLocation.objects.filter(domain=domain):
        if sql_location.metadata.get('group') == group:
            yield sql_location
