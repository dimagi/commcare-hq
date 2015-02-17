from corehq import Domain
from corehq.apps.locations.models import SQLLocation
from datetime import timedelta
from dateutil import rrule
from dateutil.rrule import MO
from corehq.apps.products.models import SQLProduct
from django.utils import html


def get_supply_points(location_id, domain):
    loc = SQLLocation.objects.get(location_id=location_id)
    location_types = [loc_type.name for loc_type in filter(
        lambda loc_type: not loc_type.administrative,
        Domain.get_by_name(domain).location_types
    )]
    if loc.location_type == 'district':
        locations = SQLLocation.objects.filter(parent=loc)
    elif loc.location_type == 'region':
        locations = SQLLocation.objects.filter(parent__parent=loc)
    elif loc.location_type in location_types:
        locations = SQLLocation.objects.filter(id=loc.id)
    else:
        locations = SQLLocation.objects.filter(domain=domain, location_type__in=location_types)
    return locations.exclude(supply_point_id__isnull=True)


def get_second_week(start_date, end_date):
    mondays = list(rrule.rrule(rrule.MONTHLY, dtstart=start_date, until=end_date, byweekday=(MO,), bysetpos=2))
    for monday in mondays:
        yield {
            'start_date': monday,
            'end_date': monday + timedelta(days=6)
        }


def make_url(report_class, domain, string_params, args):
    try:
        return html.escape(
            report_class.get_url(
                domain=domain
            ) + string_params % args
        )
    except KeyError:
        return None


def calculate_last_period(enddate):
    last_th = enddate - timedelta(days=enddate.weekday()) + timedelta(days=3, weeks=-1)
    fr_before = last_th - timedelta(days=6)
    return fr_before, last_th


def get_products_ids_assigned_to_rel_sp(domain, active_location=None):

    def filter_relevant(queryset):
        return queryset.filter(
            supply_point_id__isnull=False
        ).values_list(
            'products__product_id',
            flat=True
        )

    if active_location:
        sql_location = active_location.sql_location
        products = []
        if sql_location.supply_point_id:
            products.append(sql_location.products.values_list('product_id', flat=True))
        products += list(
            filter_relevant(sql_location.get_descendants())
        )

        return products
    else:
        return filter_relevant(SQLLocation.objects.filter(domain=domain))
