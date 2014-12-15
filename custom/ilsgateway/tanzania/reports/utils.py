from datetime import timedelta, datetime, time
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues, \
    OrganizationSummary
from django.utils import html
from dimagi.utils.dates import get_business_day_of_month
from django.utils.translation import ugettext as _


def calc_lead_time(supply_point, year=None, month=None):
    """
    The days elapsed from the day they respond "submitted" to the day they
    respond "delivered". Only include the last period for now
    """

    deliveries = SupplyPointStatus.objects.filter(
        supply_point=supply_point,
        status_type__in=[SupplyPointStatusTypes.DELIVERY_FACILITY,
                         SupplyPointStatusTypes.DELIVERY_DISTRICT],
        status_value=SupplyPointStatusValues.RECEIVED
    ).order_by("-status_date")
    if year and month:
        deliveries = deliveries.filter(status_date__month=month, status_date__year=year)
    ret = None

    if deliveries:
        latest_delivery = deliveries[0]
        previous_submissions = SupplyPointStatus.objects.filter(
            supply_point=supply_point,
            status_type__in=[SupplyPointStatusTypes.R_AND_R_FACILITY,
                             SupplyPointStatusTypes.R_AND_R_DISTRICT],
            status_value=SupplyPointStatusValues.SUBMITTED,
            status_date__lte=latest_delivery.status_date
        ).order_by("-status_date")
        if previous_submissions:
            lead_time = latest_delivery.status_date - previous_submissions[0].status_date
            if lead_time < timedelta(days=100):
                # if it's more than 100 days it's likely the wrong cycle
                ret = lead_time
    return ret


def get_this_lead_time(supply_point_id, month, year):
    lead_time = calc_lead_time(supply_point_id, month=month, year=year)
    if lead_time and timedelta(days=30) < lead_time < timedelta(days=100):
        return '%.1f' % lead_time.days
    return "None"


def get_avg_lead_time(supply_point_id, month, year):
    date = datetime(year, month, 1)
    org_sum = OrganizationSummary.objects.filter(supply_point=supply_point_id, date=date)
    if org_sum:
        if org_sum[0].average_lead_time_in_days:
            return org_sum[0].average_lead_time_in_days
    return "None"


def rr_format_percent(numerator, denominator):
            if numerator and denominator:
                return "%.1f%%" % ((float(numerator) / float(denominator)) * 100.0)
            else:
                return "No data"


def get_default_contact_for_location(domain, location_id):
    users = CommCareUser.by_domain(domain)
    for user in users:
        if user.get_domain_membership(domain).location_id == location_id:
            return user
    return None


def get_span(rr_value):
    if rr_value:
        return '<span class="icon-ok" style="color:green"/>%s'
    else:
        return '<span class="icon-warning-sign" style="color:orange"/>%s'


def make_url(report_class, domain, string_params, args):
    try:
        return html.escape(
            report_class.get_url(
                domain=domain
            ) + string_params % args
        )
    except KeyError:
        return None


def format_percent(float_number):
    if float_number:
        return '%.2f%%' % float_number
    else:
        return _('No Data')


def link_format(text, url):
    return '<a href=%s>%s</a>' % (url, text)


def decimal_format(value):
    if value == 0:
        return '<span class="icon-remove" style="color:red"/> %.0f' % value
    elif not value:
        return '<span style="color:grey"/> No Data'
    else:
        return '%.0f' % value


def float_format(value):
    if value == 0:
        return '<span class="icon-remove" style="color:red"/> %.2f' % value
    elif not value:
        return '<span style="color:grey">No Data</span>'
    else:
        return '%.2f' % value


def reporting_window(year, month):
    """
    Returns the range of time when people are supposed to report
    """
    last_of_last_month = datetime(year, month, 1) - timedelta(days=1)
    last_bd_of_last_month = datetime.combine(
        get_business_day_of_month(last_of_last_month.year, last_of_last_month.month, -1),
        time()
    )
    last_bd_of_the_month = get_business_day_of_month(year, month, -1)
    return last_bd_of_last_month, last_bd_of_the_month


def latest_status(location_id, type, value=None, month=None, year=None):
    qs = SupplyPointStatus.objects.filter(supply_point=location_id, status_type=type)
    if value:
        qs = qs.filter(status_value=value)
    if month and year:
        rw = reporting_window(year, month)
        qs = qs.filter(status_date__gt=rw[0], status_date__lte=rw[1])
    if qs.exclude(status_value="reminder_sent").exists():
        # HACK around bad data.
        qs = qs.exclude(status_value="reminder_sent")
    qs = qs.order_by("-status_date")
    return qs[0] if qs.count() else None


def latest_status_or_none(location_id, type, month, year, value=None):
    t = latest_status(location_id, type,
                      month=month,
                      year=year,
                      value=value)
    return t


def randr_value(location_id, month, year):
    latest_submit = latest_status_or_none(location_id, SupplyPointStatusTypes.R_AND_R_FACILITY,
                                          month, year, value=SupplyPointStatusValues.SUBMITTED)
    latest_not_submit = latest_status_or_none(location_id, SupplyPointStatusTypes.R_AND_R_FACILITY,
                                              month, year, value=SupplyPointStatusValues.NOT_SUBMITTED)
    if latest_submit:
        return latest_submit.status_date
    else:
        return latest_not_submit.status_date if latest_not_submit else None
