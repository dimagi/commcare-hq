from corehq import Domain
from corehq.apps.locations.models import SQLLocation
from datetime import timedelta, datetime
from dateutil import rrule
from dateutil.rrule import MO
from corehq.apps.products.models import SQLProduct
from django.utils import html
from corehq.apps.sms.api import add_msg_tags
from corehq.apps.sms.models import SMSLog, OUTGOING


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
    return locations.exclude(supply_point_id__isnull=True).values_list(*['supply_point_id'], flat=True)


def get_second_week(start_date, end_date):
    mondays = list(rrule.rrule(rrule.MONTHLY, dtstart=start_date, until=end_date, byweekday=(MO,), bysetpos=2))
    for monday in mondays:
        yield {
            'start_date': monday,
            'end_date': monday + timedelta(days=6)
        }


def get_products(program_id, products_id, domain):
    if products_id:
        return SQLProduct.objects.filter(product_id__in=products_id)
    elif program_id:
        return SQLProduct.objects.filter(program_id=program_id)
    else:
        return SQLProduct.objects.filter(is_archived=False, domain=domain)


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


def send_test_message(verified_number, text, metadata=None):
    msg = SMSLog(
        couch_recipient_doc_type=verified_number.owner_doc_type,
        couch_recipient=verified_number.owner_id,
        phone_number="+" + str(verified_number.phone_number),
        direction=OUTGOING,
        date=datetime.utcnow(),
        domain=verified_number.domain,
        text=text,
        processed=True,
        datetime_to_process=datetime.utcnow(),
        queued_timestamp=datetime.utcnow()
    )
    msg.save()
    add_msg_tags(msg, metadata)
    return True