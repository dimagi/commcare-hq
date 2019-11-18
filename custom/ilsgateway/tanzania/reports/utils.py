from datetime import timedelta, datetime, time
from django.db.models import Q
from django.db.models.aggregates import Avg
from casexml.apps.stock.models import StockTransaction
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues, \
    OrganizationSummary
from django.utils import html
from dimagi.utils.dates import get_business_day_of_month
from django.utils.translation import ugettext as _


def calc_lead_time(supply_point, start_date=None, end_date=None):
    """
    The days elapsed from the day they respond "submitted" to the day they
    respond "delivered". Only include the last period for now
    """

    deliveries = SupplyPointStatus.objects.filter(
        location_id=supply_point,
        status_type__in=[SupplyPointStatusTypes.DELIVERY_FACILITY,
                         SupplyPointStatusTypes.DELIVERY_DISTRICT],
        status_value=SupplyPointStatusValues.RECEIVED
    ).order_by("-status_date")
    if start_date and end_date:
        deliveries = deliveries.filter(status_date__range=(start_date, end_date))
    ret = None

    if deliveries:
        latest_delivery = deliveries[0]
        previous_submissions = SupplyPointStatus.objects.filter(
            location_id=supply_point,
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


def get_this_lead_time(supply_point_id, start_date, end_date):
    lead_time = calc_lead_time(supply_point_id, start_date=start_date, end_date=end_date)
    if lead_time and timedelta(days=30) < lead_time < timedelta(days=100):
        return '%.1f' % lead_time.days
    return "None"


def get_avg_lead_time(supply_point_id, start_date, end_date):
    org_sum = OrganizationSummary.objects.filter(
        location_id=supply_point_id,
        date__range=(start_date, end_date)
    ).aggregate(average_lead_time_in_days=Avg('average_lead_time_in_days'))
    if org_sum and org_sum['average_lead_time_in_days']:
        return org_sum['average_lead_time_in_days']
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


def get_span(submitted):
    if submitted:
        return '<span class="fa fa-ok" style="color:green"/>%s'
    else:
        return '<span class="fa fa-exclamation-triangle" style="color:orange"/>%s'


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
        return '%.1f%%' % float_number
    else:
        return _('No Data')


def link_format(text, url):
    return '<a href=%s target="_blank">%s</a>' % (url, text)


def decimal_format(value):
    if value == 0:
        return '<span class="fa fa-remove" style="color:red"/> %.0f' % value
    elif not value:
        return '<span style="color:grey"/> No Data'
    else:
        return '%.0f' % value


def float_format(value):
    if value == 0:
        return '<span class="fa fa-remove" style="color:red"/> %.2f' % value
    elif not value:
        return '<span style="color:grey">No Data</span>'
    else:
        return '%.2f' % value


def reporting_window(start_date, end_date):
    """
    Returns the range of time when people are supposed to report
    """
    last_of_last_month = datetime(start_date.year, start_date.month, 1) - timedelta(days=1)
    last_bd_of_last_month = datetime.combine(
        get_business_day_of_month(last_of_last_month.year, last_of_last_month.month, -1),
        time()
    )
    last_bd_of_the_month = get_business_day_of_month(end_date.year, end_date.month, -1)
    return last_bd_of_last_month, last_bd_of_the_month


def latest_status(location_id, type, value=None, start_date=None, end_date=None):
    qs = SupplyPointStatus.objects.filter(location_id=location_id, status_type=type)
    if value:
        qs = qs.filter(status_value=value)

    if start_date and end_date:
        rr = reporting_window(start_date, end_date)
        qs = qs.filter(status_date__gt=rr[0], status_date__lte=rr[1]).exclude(status_value="reminder_sent")

    qs = qs.order_by("-status_date")
    return qs.first()


def latest_status_or_none(location_id, type, start_date, end_date, value=None):
    return latest_status(
        location_id,
        type,
        start_date=start_date,
        end_date=end_date,
        value=value
    )


def randr_value(location_id, start_date, end_date):
    latest_submit = latest_status_or_none(location_id, SupplyPointStatusTypes.R_AND_R_FACILITY,
                                          start_date, end_date, value=SupplyPointStatusValues.SUBMITTED)
    if latest_submit:
        return True, latest_submit.status_date
    else:
        latest_not_submit = latest_status_or_none(location_id, SupplyPointStatusTypes.R_AND_R_FACILITY,
                                          start_date, end_date, value=SupplyPointStatusValues.NOT_SUBMITTED)
        return False, latest_not_submit.status_date if latest_not_submit else None


def get_hisp_resp_rate(location):
    statuses = SupplyPointStatus.objects.filter(
        location_id=location.location_id,
        status_type=SupplyPointStatusTypes.SOH_FACILITY
    )
    if not statuses:
        return None
    status_month_years = set([(x.status_date.month, x.status_date.year) for x in statuses])
    denom = len(status_month_years)
    num = 0
    for s in status_month_years:
        f = statuses.filter(status_date__month=s[0], status_date__year=s[1]).filter(
            Q(status_value=SupplyPointStatusValues.SUBMITTED) |
            Q(status_value=SupplyPointStatusValues.NOT_SUBMITTED) |
            Q(status_value=SupplyPointStatusValues.RECEIVED) |
            Q(status_value=SupplyPointStatusValues.NOT_RECEIVED)
        ).order_by("-status_date")
        if f.count():
            num += 1

    return float(num) / float(denom), num, denom


def get_last_reported(supplypoint, domain, enddate):
    from custom.ilsgateway.tanzania.reports.stock_on_hand import _reported_on_time, OnTimeStates
    last_bd_of_the_month = get_business_day_of_month(enddate.year,
                                                     enddate.month,
                                                     -1)
    st = StockTransaction.objects.filter(
        case_id=supplypoint,
        type='stockonhand',
        report__date__lte=last_bd_of_the_month,
        report__domain=domain
    ).order_by('-report__date').first()
    last_of_last_month = datetime(enddate.year, enddate.month, 1) - timedelta(days=1)
    last_bd_of_last_month = datetime.combine(get_business_day_of_month(last_of_last_month.year,
                                             last_of_last_month.month,
                                             -1), time())
    if st:
        sts = _reported_on_time(last_bd_of_last_month, st.report.date)
        return sts, st.report.date.date()
    else:
        sts = OnTimeStates.NO_DATA
        return sts, None


def calculate_months_remaining(stock_state, quantity):
    consumption = stock_state.daily_consumption
    if consumption is not None and consumption > 0 and quantity is not None:
        return float(quantity) / float(30 * consumption)
    elif quantity == 0:
        return 0
