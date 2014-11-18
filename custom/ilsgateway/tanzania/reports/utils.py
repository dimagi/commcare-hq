from datetime import timedelta, datetime
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues, \
    OrganizationSummary
from django.utils import html



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