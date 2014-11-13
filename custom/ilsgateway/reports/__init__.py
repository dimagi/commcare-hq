from datetime import datetime, timedelta, time
from functools import partial
from django.utils.formats import date_format
from corehq.apps.users.models import CommCareUser
from dimagi.utils.dates import get_business_day_of_month
from corehq.apps.locations.models import Location
from corehq.apps.reports.graph_models import PieChart
from corehq.apps.commtrack.models import SQLProduct
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from custom.ilsgateway.models import GroupSummary, SupplyPointStatusTypes, DeliveryGroups, \
    ProductAvailabilityData, ProductAvailabilityDashboardChart, OrganizationSummary, SupplyPointStatus, \
    SupplyPointStatusValues
from django.utils.translation import ugettext as _
from django.utils import html
from django.utils.dateformat import format


def format_percent(float_number):
    if float_number:
        return '%.2f%%' % float_number
    else:
        return _('No Data')


def link_format(text, url):
    return '<a href=%s>%s</a>' % (url, text)


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


def _latest_status_or_none(location_id, type, month, year, value=None):
    t = latest_status(location_id, type,
                      month=month,
                      year=year,
                      value=value)
    return t.status_date if t else None


def randr_value(location_id, month, year):
    latest_submit = _latest_status_or_none(location_id, SupplyPointStatusTypes.R_AND_R_FACILITY,
                                           month, year, value=SupplyPointStatusValues.SUBMITTED)
    latest_not_submit = _latest_status_or_none(location_id, SupplyPointStatusTypes.R_AND_R_FACILITY,
                                               month, year, value=SupplyPointStatusValues.NOT_SUBMITTED)
    if latest_submit:
        return latest_submit
    else:
        return latest_not_submit


class ILSData(object):
    show_table = False
    show_chart = True
    title_url = None
    title_url_name = None

    chart_config = {
        'on_time': {
            'color': 'green',
            'display': 'Submitted On Time'
        },
        'late': {
            'color': 'orange',
            'display': 'Submitted Late'
        },
        'not_submitted': {
            'color': 'red',
            'display': "Haven't Submitted "
        },
        'del_received': {
            'color': 'green',
            'display': 'Delivery Received',
        },
        'del_not_received': {
            'color': 'red',
            'display': 'Delivery Not Received',
        },
        'sup_received': {
            'color': 'green',
            'display': 'Supervision Received',
        },
        'sup_not_received': {
            'color': 'red',
            'display': 'Supervision Not Received',
        },
        'not_responding': {
            'color': '#8b198b',
            'display': "Didn't Respond"
        },
    }
    vals_config = {
        SupplyPointStatusTypes.SOH_FACILITY: ['on_time', 'late', 'not_submitted', 'not_responding'],
        SupplyPointStatusTypes.DELIVERY_FACILITY: ['del_received', 'del_not_received', 'not_responding'],
        SupplyPointStatusTypes.R_AND_R_FACILITY: ['on_time', 'late', 'not_submitted', 'not_responding'],
        SupplyPointStatusTypes.SUPERVISION_FACILITY: ['sup_received', 'sup_not_received', 'not_responding']
    }

    def __init__(self, config=None, css_class='row_chart'):
        self.config = config or {}
        self.css_class = css_class

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        raise NotImplementedError

    @property
    def charts(self):
        data = self.rows

        ret = []
        sum_all = 0
        colors = []
        if data:
            for key in self.vals_config[data.title]:
                if getattr(data, key, None):
                    sum_all = sum_all + getattr(data, key)
            for key in self.vals_config[data.title]:
                if getattr(data, key, None):
                    entry = {}
                    entry['value'] = float(getattr(data, key)) * 100 / float((sum_all or 1))
                    colors.append(self.chart_config[key]['color'])
                    entry['label'] = self.chart_config[key]['display']
                    params = (
                        entry['value'],
                        getattr(data, key), entry['label'],
                        self.config['startdate'].strftime("%b %Y")
                    )
                    entry['description'] = "%.2f%% (%d) %s (%s)" % params

                    ret.append(entry)
        return [PieChart('', '', ret, color=colors)]


class RandRSubmissionData(ILSData):
    title = 'R&R Submission'
    slug = 'rr_submission'

    @property
    def rows(self):
        rr_data = []
        if self.config['org_summary']:
            rr_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.R_AND_R_FACILITY,
                                               org_summary=self.config['org_summary'])
        return rr_data


class DistrictSummaryData(ILSData):
    title = 'District Summary'
    slug = 'district_summary'
    show_table = True
    show_chart = False

    @property
    def rows(self):

        if self.config['org_summary']:

            def prepare_processing_info(data):
                numbers = {}
                numbers['total'] = data[0] - (data[1].total + data[2].total)
                numbers['complete'] = 0
                return numbers

            org_summary = self.config['org_summary']
            total = org_summary.total_orgs
            avg_lead_time = org_summary.average_lead_time_in_days
            if avg_lead_time:
                avg_lead_time = "%.1f" % avg_lead_time

            endmonth = self.config['enddate'].month
            dg = DeliveryGroups(month=endmonth)

            rr_data = RandRSubmissionData(config=self.config).rows
            delivery_data = DeliverySubmissionData(config=self.config).rows

            submitting_group = dg.current_submitting_group(month=endmonth)
            processing_group = dg.current_processing_group(month=endmonth)
            delivery_group = dg.current_delivering_group(month=endmonth)

            processing_numbers = prepare_processing_info([total, rr_data, delivery_data])

            return {
                "processing_total": processing_numbers['total'],
                "processing_complete": processing_numbers['complete'],
                "submitting_total": rr_data.total,
                "submitting_complete": rr_data.complete,
                "delivery_total": delivery_data.total,
                "delivery_complete": delivery_data.complete,
                "delivery_group": delivery_group,
                "submitting_group": submitting_group,
                "processing_group": processing_group,
                "total": total,
                "avg_lead_time": avg_lead_time,
            }
        else:
            return None


class SohSubmissionData(ILSData):
    title = 'SOH Submission'
    slug = 'soh_submission'

    @property
    def rows(self):
        soh_data = []
        if self.config['org_summary']:
            soh_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.SOH_FACILITY,
                                                org_summary=self.config['org_summary'])
        return soh_data


class DeliverySubmissionData(ILSData):
    title = 'Delivery Submission'
    slug = 'delivery_submission'

    @property
    def rows(self):
        del_data = []
        if self.config['org_summary']:
            del_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.DELIVERY_FACILITY,
                                                org_summary=self.config['org_summary'])
        return del_data


class ProductAvailabilitySummary(ILSData):
    title = 'Product Availability'
    slug = 'product_availability'

    def __init__(self, config, css_class, chart_stacked=True):
        super(ProductAvailabilitySummary, self).__init__(config, css_class)
        self.chart_stacked = chart_stacked

    @property
    def rows(self):
        product_availability = []
        if self.config['org_summary']:
            product_availability = ProductAvailabilityData.objects.filter(
                date__range=(self.config['startdate'], self.config['enddate']),
                supply_point=self.config['org_summary'].supply_point)
        return product_availability

    @property
    def charts(self):
        product_dashboard = ProductAvailabilityDashboardChart()
        product_availability = self.rows

        def convert_product_data_to_stack_chart(rows, chart_config):
            ret_data = []
            for k in ['Stocked out', 'Not Stocked out', 'No Stock Data']:
                datalist = []
                for product in rows:
                    prd_code = SQLProduct.objects.get(product_id=product.product).code
                    if k == 'No Stock Data':
                        datalist.append([prd_code, product.without_data])
                    elif k == 'Stocked out':
                        datalist.append([prd_code, product.without_stock])
                    elif k == 'Not Stocked out':
                        datalist.append([prd_code, product.with_stock])
                ret_data.append({'color': chart_config.label_color[k], 'label': k, 'data': datalist})
            return ret_data

        chart = MultiBarChart('', x_axis=Axis('Products'), y_axis=Axis(''))
        chart.rotateLabels = -45
        chart.marginBottom = 120
        chart.stacked = self.chart_stacked
        for row in convert_product_data_to_stack_chart(product_availability, product_dashboard):
            chart.add_dataset(row['label'], [
                {'x': r[0], 'y': r[1]}
                for r in sorted(row['data'], key=lambda x: x[0])], color=row['color']
            )
        return [chart]


class RRStatus(ILSData):
    show_table = True
    title = "R&R Status"
    slug = "rr_status"
    show_chart = False

    @property
    def rows(self):
        def format_percent(numerator, denominator):
            if numerator and denominator:
                return "%.1f%%" % ((float(numerator) / float(denominator)) * 100.0)
            else:
                return "No data"
        rows = []
        location = Location.get(self.config['location_id'])
        for child in location.children:
            try:
                org_summary = OrganizationSummary.objects.get(
                    date__range=(self.config['startdate'],
                                 self.config['enddate']),
                    supply_point=child._id
                )
            except OrganizationSummary.DoesNotExist:
                return []

            rr_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.R_AND_R_FACILITY,
                                               org_summary=org_summary)

            fp_partial = partial(format_percent, denominator=rr_data.total)

            total_responses = 0
            total_possible = 0
            group_summaries = GroupSummary.objects.filter(
                org_summary__date__lte=datetime(int(self.config['year']), int(self.config['month']), 1),
                org_summary__supply_point=child._id, title='rr_fac'
            )
            for g in group_summaries:
                if g:
                    total_responses += g.responded
                    total_possible += g.total
            hist_resp_rate = format_percent(total_responses, total_possible)
            try:
                from custom.ilsgateway import RRreport
                url = html.escape(RRreport.get_url(
                    domain=self.config['domain']) +
                    '?location_id=%s&month=%s&year=%s' %
                    (child._id, self.config['month'], self.config['year']))
            except KeyError:
                url = None

            rows.append(
                [
                    link_format(child.name, url),
                    fp_partial(rr_data.on_time),
                    fp_partial(rr_data.late),
                    fp_partial(rr_data.not_submitted),
                    fp_partial(rr_data.not_responding),
                    hist_resp_rate
                ])

        return rows

    @property
    def headers(self):
        return [
            'Name',
            '% Facilities Submitting R&R On Time',
            "% Facilities Submitting R&R Late",
            "% Facilities With R&R Not Submitted",
            "% Facilities Not Responding To R&R Reminder",
            "Historical Response Rate"
        ]


class RRReportingHistory(ILSData):
    show_table = True
    title = "R&R Reporting History"
    slug = "rr_reporting_history"
    show_chart = False

    @property
    def rows(self):
        def format_percent(numerator, denominator):
            if numerator and denominator:
                return "%.1f%%" % ((float(numerator) / float(denominator)) * 100.0)
            else:
                return "No data"
        rows = []
        location = Location.get(self.config['location_id'])
        dg = DeliveryGroups().submitting(location.children, int(self.config['month']))
        for child in dg:
            total_responses = 0
            total_possible = 0
            group_summaries = GroupSummary.objects.filter(
                org_summary__date__lte=datetime(int(self.config['year']), int(self.config['month']), 1),
                org_summary__supply_point=child._id, title='rr_fac'
            )
            for g in group_summaries:
                if g:
                    total_responses += g.responded
                    total_possible += g.total
            hist_resp_rate = format_percent(total_responses, total_possible)
            try:
                from custom.ilsgateway import RRreport
                url = html.escape(RRreport.get_url(
                    domain=self.config['domain']) +
                    '?location_id=%s&month=%s&year=%s' %
                    (child._id, self.config['month'], self.config['year']))
            except KeyError:
                url = None
            rr_value = randr_value(child._id, int(self.config['month']), int(self.config['year']))

            def _default_contact(location_id):
                users = CommCareUser.by_domain(self.config['domain'])
                for user in users:
                    if user.get_domain_membership(self.config['domain']).location_id == location_id:
                        return user
                return None

            contact = _default_contact(child._id)
            if contact:
                role = contact.user_data.get('role') or ""
                contact_string = "%s %s (%s) %s" % (contact.first_name, contact.last_name, role,
                                                    contact.default_phone_number)
            else:
                contact_string = ""

            def get_span(rr_value):
                if rr_value:
                    return '<span class="icon-ok" style="color:green"/>%s'
                else:
                    return '<span class="icon-warning-sign" style="color:orange"/>%s'

            rows.append(
                [
                    child.site_code,
                    child.name,
                    get_span(rr_value) % (format(rr_value, "d M Y") if rr_value else "Not reported"),
                    contact_string,
                    hist_resp_rate
                ])

        return rows

    @property
    def headers(self):
        return [
            'Code',
            'Facility Name',
            'R&R Status',
            'Contact',
            'Historical Response Rate'
        ]


class ILSMixin(object):

    @property
    def report_facilities_url(self):
        return None

    @property
    def report_stockonhand_url(self):
        return None

    @property
    def report_rand_url(self):
        return None

    @property
    def report_supervision_url(self):
        return None

    @property
    def report_delivery_url(self):
        return None

    @property
    def report_unrecognizedmessages_url(self):
        return None
