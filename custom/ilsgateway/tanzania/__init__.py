from datetime import datetime
from dateutil import rrule
from dateutil.relativedelta import relativedelta
import pytz
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.sqlreport import SqlTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.style.decorators import use_nvd3
from couchexport.models import Format
from custom.common import ALL_OPTION
from custom.ilsgateway.models import SupplyPointStatusTypes, OrganizationSummary
from corehq.apps.reports.graph_models import PieChart
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from custom.ilsgateway.tanzania.reports.utils import make_url
from dimagi.utils.parsing import ISO_DATE_FORMAT


class ILSPieChart(PieChart):

    def __init__(self, title, key, values, color=None):
        super(ILSPieChart, self).__init__(title, key, values, color)
        self.data = values


class ILSData(object):
    show_table = False
    show_chart = True
    title_url = None
    title_url_name = None
    subtitle = None
    default_rows = 10
    searchable = False
    use_datatables = False

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
            data = data[0]
            for key in self.vals_config[data.title]:
                if getattr(data, key, None):
                    sum_all = sum_all + getattr(data, key)
            for key in self.vals_config[data.title]:
                if getattr(data, key, None):
                    entry = {}
                    entry['value'] = round(float(getattr(data, key)) * 100 / float((sum_all or 1)), 1)
                    colors.append(self.chart_config[key]['color'])
                    entry['label'] = self.chart_config[key]['display']
                    params = (
                        entry['value'],
                        getattr(data, key), entry['label'],
                        self.config['startdate'].strftime("%b %Y")
                    )
                    entry['description'] = "%.1f%% (%d) %s (%s)" % params

                    ret.append(entry)
        chart = ILSPieChart('', '', ret, color=colors)
        chart.marginLeft = 10
        chart.marginRight = 10
        chart.height = 500
        return [chart]


class ILSMixin(object):
    report_facilities_url = None
    report_stockonhand_url = None
    report_rand_url = None
    report_supervision_url = None
    report_delivery_url = None


class ILSDateSpan(DateSpan):

    @classmethod
    def get_date(cls, type=None, month_or_quarter=None, year=None, format=ISO_DATE_FORMAT,
                 inclusive=True, timezone=pytz.utc):
        """
        Generate a DateSpan object given type, month or quarter and year.

            april = DateSpan.get_date(1, 04, 2013)
            First Quarter: DateSpan.from_month(2, 1, 2015)
            2015: DateSpan.from_month(3, None, 2015)
        """
        if month_or_quarter is None:
            month_or_quarter = datetime.datetime.date.today().month
        if year is None:
            year = datetime.datetime.date.today().year
        assert isinstance(month_or_quarter, int) and isinstance(year, int)
        if type == 3:
            start = datetime(int(year), 1, 1)
            end = datetime(int(year), 12, 31)
        elif type == 2:
            quarters = list(rrule.rrule(rrule.MONTHLY,
                                        bymonth=(1, 4, 7, 10),
                                        bysetpos=-1,
                                        dtstart=datetime(year, 1, 1),
                                        count=5))

            start = quarters[month_or_quarter - 1]
            end = quarters[month_or_quarter] - relativedelta(days=1)
        else:
            start = datetime(year, month_or_quarter, 1)
            end = start + relativedelta(months=1) - relativedelta(days=1)
        return DateSpan(start, end, format, inclusive, timezone)


class MonthQuarterYearMixin(object):
    _datespan = None

    @property
    def datespan(self):
        if self._datespan is None:
            datespan = ILSDateSpan.get_date(self.type, self.first, self.second)
            self.request.datespan = datespan
            self.context.update(dict(datespan=datespan))
            self._datespan = datespan
        return self._datespan

    @property
    def type(self):
        """
            We have a 3 possible type:
            1 - month
            2 - quarter
            3 - year
        """
        if self.request_params.get('datespan_type'):
            return int(self.request_params['datespan_type'])
        else:
            return 1

    @property
    def first(self):
        """
            If we choose type 1 in this we get a month [00-12]
            If we choose type 2 we get quarter [1-4]
            This property is unused when we choose type 3
        """
        if self.request_params.get('datespan_first'):
            return int(self.request_params['datespan_first'])
        else:
            return datetime.utcnow().month

    @property
    def second(self):
        if self.request_params.get('datespan_second'):
            return int(self.request_params['datespan_second'])
        else:
            return datetime.utcnow().year


class MultiReport(SqlTabularReport, ILSMixin, CustomProjectReport,
                  ProjectReportParametersMixin, MonthQuarterYearMixin):
    title = ''
    report_template_path = "ilsgateway/multi_report.html"
    flush_layout = True
    with_tabs = False
    use_datatables = False
    exportable = False
    base_template = 'ilsgateway/base_template.html'
    emailable = False

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(MultiReport, self).decorator_dispatcher(request, *args, **kwargs)

    @classmethod
    def get_url(cls, domain=None, render_as=None, **kwargs):

        url = super(MultiReport, cls).get_url(domain=domain, render_as=None, kwargs=kwargs)
        request = kwargs.get('request')
        user = getattr(request, 'couch_user', None)

        dm = user.get_domain_membership(domain) if user else None
        if dm:
            if dm.program_id:
                program_id = dm.program_id
            else:
                program_id = 'all'

            url = '%s?location_id=%s&filter_by_program=%s' % (
                url,
                dm.location_id if dm.location_id else SQLLocation.objects.get(
                    domain=domain, location_type__name='MOHSW'
                ).location_id,
                program_id if program_id else ''
            )

        return url

    @property
    def location(self):
        if hasattr(self, 'request') and self.request.GET.get('location_id', ''):
            return SQLLocation.objects.get(location_id=self.request.GET.get('location_id', ''))
        else:
            return SQLLocation.objects.filter(location_type__name='MOHSW', domain=self.domain)[0]

    @property
    @memoized
    def rendered_report_title(self):
        return self.title

    @property
    @memoized
    def data_providers(self):
        return []

    @property
    def title_month(self):
        days = self.datespan.enddate - self.datespan.startdate
        if days.days <= 31:
            return self.datespan.startdate.strftime('%B, %Y')
        else:
            return '{0} - {1}'.format(self.datespan.startdate.strftime('%B'),
                                      self.datespan.enddate.strftime('%B, %Y'))

    @property
    def report_config(self):
        org_summary = OrganizationSummary.objects.filter(
            date__range=(self.datespan.startdate, self.datespan.enddate),
            location_id=self.location.location_id
        )
        config = dict(
            domain=self.domain,
            org_summary=org_summary if len(org_summary) > 0 else None,
            startdate=self.datespan.startdate,
            enddate=self.datespan.enddate,
            datespan_type=self.type,
            datespan_first=self.first,
            datespan_second=self.second,
            location_id=self.location.location_id,
            soh_month=True if self.request.GET.get('soh_month', '') == 'True' else False,
            products=[],
            program='',
            prd_part_url='',
            timezone=self.timezone
        )

        if 'filter_by_program' in self.request.GET:
            program = self.request.GET.get('filter_by_program', '')
            if program and program != ALL_OPTION:
                products_list = self.request.GET.getlist('filter_by_product')
                if (products_list and products_list[0] == ALL_OPTION) or not products_list:
                    products = SQLProduct.objects.filter(program_id=program, is_archived=False)\
                        .order_by('code')\
                        .values_list('product_id', flat=True)
                    prd_part_url = '&filter_by_product=%s' % ALL_OPTION
                else:
                    products = SQLProduct.objects.filter(
                        pk__in=products_list,
                        is_archived=False
                    ).order_by('code').values_list('product_id', flat=True)

                    prd_part_url = "".join(["&filter_by_product=%s" % product for product in products_list])

            else:
                products = SQLProduct.objects.filter(
                    domain=self.domain,
                    is_archived=False
                ).order_by('code').values_list('product_id', flat=True)

                prd_part_url = "&filter_by_product="
            config.update(dict(products=products, program=program, prd_part_url=prd_part_url))

        return config

    @property
    def report_context(self):
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title,
            'report_facilities_url': self.report_facilities_url,
            'location_type': self.location.location_type.name if self.location else None
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
                datatables=data_provider.use_datatables,
                slug=data_provider.slug,
                headers=headers,
                rows=rows,
                total_row=total_row,
                start_at_row=0,
                subtitle=data_provider.subtitle,
                location=self.location.id if self.location else '',
                default_rows=data_provider.default_rows,
                searchable=data_provider.searchable
            ),
            show_table=data_provider.show_table,
            show_chart=data_provider.show_chart,
            charts=data_provider.charts if data_provider.show_chart else [],
            chart_span=12,
            css_class=data_provider.css_class,
        )
        return context

    @property
    def export_table(self):
        default_value = [['Sheet1', [[]]]]
        self.export_format_override = self.request.GET.get('format', Format.XLS)
        reports = [r['report_table'] for r in self.report_context['reports']]

        export = [self._export_table(r['title'], r['headers'], r['rows'], total_row=r['total_row'])
                  for r in reports if r['headers']]
        return export if export else default_value

    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        replace = ''

        for row in rows:
            for index, value in enumerate(row):
                row[index] = GenericTabularReport._strip_tags(value)

        # make headers and subheaders consistent
        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, table]


class DetailsReport(MultiReport):
    with_tabs = True
    flush_layout = True
    exportable = True

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True

    @property
    def with_tabs(self):
        return self.location and self.location.location_type.name.upper() == 'FACILITY'

    @property
    def report_context(self):
        context = super(DetailsReport, self).report_context
        if 'location_id' in self.request_params:
            context.update(
                dict(
                    report_stockonhand_url=self.report_stockonhand_url,
                    report_rand_url=self.report_rand_url,
                    report_supervision_url=self.report_supervision_url,
                    report_delivery_url=self.report_delivery_url,
                    with_tabs=True
                )
            )
        return context

    def ils_make_url(self, cls):
        params = '?location_id=%s&filter_by_program=%s&datespan_type=%s&datespan_first=%s&datespan_second=%s'
        return make_url(cls, self.domain, params, (
            self.request.GET.get('location_id'),
            self.request.GET.get('filter_by_program'),
            self.request.GET.get('datespan_type', ''),
            self.request.GET.get('datespan_first', ''),
            self.request.GET.get('datespan_second', ''),
        ))

    @property
    def report_stockonhand_url(self):
        from custom.ilsgateway.tanzania.reports.stock_on_hand import StockOnHandReport
        return self.ils_make_url(StockOnHandReport)

    @property
    def report_rand_url(self):
        from custom.ilsgateway.tanzania.reports.randr import RRreport
        return self.ils_make_url(RRreport)

    @property
    def report_supervision_url(self):
        from custom.ilsgateway.tanzania.reports.supervision import SupervisionReport
        return self.ils_make_url(SupervisionReport)

    @property
    def report_delivery_url(self):
        from custom.ilsgateway.tanzania.reports.delivery import DeliveryReport
        return self.ils_make_url(DeliveryReport)
