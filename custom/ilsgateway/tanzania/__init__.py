from corehq.apps.reports.sqlreport import SqlTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, MonthYearMixin
from custom.ilsgateway.models import SupplyPointStatusTypes, OrganizationSummary
from corehq.apps.reports.graph_models import PieChart
from dimagi.utils.decorators.memoized import memoized
from custom.ilsgateway.tanzania.reports.utils import make_url
from django.utils import html


class ILSData(object):
    show_table = False
    show_chart = True
    title_url = None
    title_url_name = None
    subtitle = None

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


class MultiReport(SqlTabularReport, ILSMixin, CustomProjectReport, ProjectReportParametersMixin, MonthYearMixin):
    title = ''
    report_template_path = "ilsgateway/multi_report.html"
    flush_layout = True
    with_tabs = False
    use_datatables = False

    @property
    @memoized
    def rendered_report_title(self):
        return self.title

    @property
    @memoized
    def data_providers(self):
        return []

    @property
    def report_config(self):
        org_summary = OrganizationSummary.objects.filter(date__range=(self.datespan.startdate,
                                                                      self.datespan.enddate),
                                                         supply_point=self.request.GET.get('location_id'))
        return dict(
            domain=self.domain,
            org_summary=org_summary[0] if len(org_summary) > 0 else None,
            startdate=self.datespan.startdate,
            enddate=self.datespan.enddate,
            month=self.request_params['month'] if 'month' in self.request_params else '',
            year=self.request_params['year'] if 'year' in self.request_params else '',
            location_id=self.request.GET.get('location_id'),
            soh_month=True if self.request.GET.get('soh_month', '') == 'True' else False
        )

    @property
    def report_context(self):
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title,
            'report_facilities_url': self.report_facilities_url,
        }

        return context

    def get_report_context(self, data_provider):

        total_row = []
        self.data_source = data_provider
        headers = []
        rows = []
        if not self.needs_filters and data_provider.show_table:
            headers = data_provider.headers
            rows = data_provider.rows

        context = dict(
            report_table=dict(
                title=data_provider.title,
                title_url=data_provider.title_url,
                title_url_name=data_provider.title_url_name,
                slug=data_provider.slug,
                headers=headers,
                rows=rows,
                datatables=self.use_datatables,
                total_row=total_row,
                start_at_row=0,
                subtitle=data_provider.subtitle,
            ),
            show_table=data_provider.show_table,
            show_chart=data_provider.show_chart,
            charts=data_provider.charts if data_provider.show_chart else [],
            chart_span=12,
            css_class=data_provider.css_class
        )
        return context


class DetailsReport(MultiReport):
    with_tabs = True
    flush_layout = True

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True

    @property
    def report_context(self):
        context = super(DetailsReport, self).report_context
        context.update(
            dict(
                report_stockonhand_url=self.report_stockonhand_url,
                report_rand_url=self.report_rand_url,
                report_supervision_url=self.report_supervision_url,
                report_delivery_url=self.report_delivery_url,
                report_unrecognizedmessages_url=self.report_unrecognizedmessages_url,
                with_tabs=True
            )
        )
        return context

    @property
    def report_stockonhand_url(self):
        from custom.ilsgateway.tanzania.reports.stock_on_hand import StockOnHandReport
        return html.escape(make_url(StockOnHandReport,
                                    self.domain,
                                    '?location_id=%s&month=%s&year=%s',
                                    (self.request_params['location_id'],
                                     self.request_params['month'],
                                     self.request_params['year'])))

    @property
    def report_rand_url(self):
        from custom.ilsgateway.tanzania.reports.randr import RRreport
        return html.escape(make_url(RRreport,
                                    self.domain,
                                    '?location_id=%s&month=%s&year=%s',
                                    (self.request_params['location_id'],
                                     self.request_params['month'],
                                     self.request_params['year'])))

    @property
    def report_supervision_url(self):
        from custom.ilsgateway.tanzania.reports.supervision import SupervisionReport
        return html.escape(make_url(SupervisionReport,
                                    self.domain,
                                    '?location_id=%s&month=%s&year=%s',
                                    (self.request_params['location_id'],
                                     self.request_params['month'],
                                     self.request_params['year'])))

    @property
    def report_delivery_url(self):
        from custom.ilsgateway.tanzania.reports.delivery import DeliveryReport
        return html.escape(make_url(DeliveryReport,
                                    self.domain,
                                    '?location_id=%s&month=%s&year=%s',
                                    (self.request_params['location_id'],
                                     self.request_params['month'],
                                     self.request_params['year'])))

    @property
    def report_unrecognizedmessages_url(self):
        return None
