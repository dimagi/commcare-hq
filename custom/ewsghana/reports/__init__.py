from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.template.loader import render_to_string
import pytz
from corehq import Domain
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.models import Program
from corehq.apps.reports.commtrack.standard import CommtrackReportMixin
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.graph_models import LineChart, MultiBarChart, PieChart
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from custom.ewsghana.filters import ProductByProgramFilter, EWSDateFilter
from dimagi.utils.dates import DateSpan, force_to_datetime
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import SQLLocation, LocationType
from custom.ewsghana.utils import get_supply_points, filter_slugs_by_role, ews_date_format
from casexml.apps.stock.models import StockTransaction
from dimagi.utils.parsing import ISO_DATE_FORMAT


def get_url(view_name, text, domain):
    return '<a href="%s">%s</a>' % (reverse(view_name, args=[domain]), text)


def get_url_with_location(view_name, text, location_id, domain):
    return '<a href="%s?location_id=%s">%s</a><h4><strong>' % (
        reverse(view_name, args=[domain]),
        location_id,
        text
    )

class EWSLineChart(LineChart):
    template_partial = 'ewsghana/partials/ews_line_chart.html'

    def __init__(self, title, x_axis, y_axis, y_tick_values=None):
        super(EWSLineChart, self).__init__(title, x_axis, y_axis)
        self.y_tick_values = y_tick_values or []


class EWSPieChart(PieChart):
    template_partial = 'ewsghana/partials/ews_pie_chart.html'


class EWSMultiBarChart(MultiBarChart):
    template_partial = 'ewsghana/partials/ews_multibar_chart.html'


class EWSData(object):
    show_table = False
    show_chart = False
    title = ''
    slug = ''
    use_datatables = False
    custom_table = False
    default_rows = 10

    def __init__(self, config=None):
        self.config = config or {}
        super(EWSData, self).__init__()

    def percent_fn(self, x, y):
        return "%(p).2f%%" % \
            {
                "p": (100 * float(y or 0) / float(x or 1))
            }

    @property
    def headers(self):
        return []

    @property
    def location_id(self):
        return self.config.get('location_id')

    @property
    @memoized
    def location(self):
        location_id = self.location_id
        if not location_id:
            return None
        return SQLLocation.objects.get(location_id=location_id)

    @property
    def rows(self):
        raise NotImplementedError

    @property
    def domain(self):
        return self.config.get('domain')

    @memoized
    def reporting_types(self):
        return LocationType.objects.filter(domain=self.domain, administrative=False)

    def unique_products(self, locations, all=False):
        if self.config['products'] and not all:
            return SQLProduct.objects.filter(
                pk__in=locations.values_list('_products', flat=True),
            ).filter(pk__in=self.config['products']).exclude(is_archived=True)
        elif self.config['program'] and not all:
            return SQLProduct.objects.filter(
                pk__in=locations.values_list('_products', flat=True),
                program_id=self.config['program']
            ).exclude(is_archived=True)
        else:
            return SQLProduct.objects.filter(
                pk__in=locations.values_list('_products', flat=True)
            ).exclude(is_archived=True)


class ReportingRatesData(EWSData):
    def get_supply_points(self, location_id=None):
        location = SQLLocation.objects.get(location_id=location_id) if location_id else self.location

        location_types = self.reporting_types()
        if location.location_type.name == 'district':
            locations = SQLLocation.objects.filter(parent=location)
        elif location.location_type.name == 'region':
            loc_types = location_types.exclude(name='Central Medical Store')
            locations = SQLLocation.objects.filter(
                Q(parent__parent=location, location_type__in=loc_types) |
                Q(parent=location, location_type__in=loc_types)
            )
        elif location.location_type in location_types:
            locations = SQLLocation.objects.filter(id=location.id)
        else:
            types = ['Central Medical Store', 'Regional Medical Store', 'Teaching Hospital']
            loc_types = location_types.filter(name__in=types)
            locations = SQLLocation.objects.filter(
                domain=self.domain,
                location_type__in=loc_types
            )
        return locations.exclude(supply_point_id__isnull=True).exclude(is_archived=True)

    def supply_points_list(self, location_id=None):
        return self.get_supply_points(location_id).values_list('supply_point_id')

    def reporting_supply_points(self, supply_points=None):
        if not supply_points:
            supply_points = self.get_supply_points().values_list('supply_point_id', flat=True)
        return StockTransaction.objects.filter(
            case_id__in=supply_points,
            report__date__range=[self.config['startdate'], self.config['enddate']]
        ).distinct('case_id').values_list('case_id', flat=True)

    def datetext(self):
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return "last %d days" % (today - self.config['startdate']).days if today == self.config['enddate'] else\
            "%s to %s" % (self.config['startdate'].strftime("%Y-%m-%d"),
                          self.config['enddate'].strftime("%Y-%m-%d"))


class EWSDateSpan(DateSpan):

    @classmethod
    def get_date(cls, type=None, month_or_week=None, year=None, format=ISO_DATE_FORMAT,
                 inclusive=True, timezone=pytz.utc):
        if month_or_week is None:
            month_or_week = datetime.datetime.date.today().month
        if year is None:
            year = datetime.datetime.date.today().year
        if type == 2:
            days = month_or_week.split('|')
            start = force_to_datetime(days[0])
            end = force_to_datetime(days[1])
        else:
            start = datetime(year, month_or_week, 1, 0, 0, 0)
            print start
            end = start + relativedelta(months=1) - relativedelta(days=1)
        return DateSpan(start, end, format, inclusive, timezone)


class MonthWeekMixin(object):
    _datespan = None

    @property
    def datespan(self):
        if self._datespan is None:
            datespan = EWSDateSpan.get_date(self.type, self.first, self.second)
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
        if 'datespan_type' in self.request_params:
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
        if 'datespan_first' in self.request_params:
            try:
                return int(self.request_params['datespan_first'])
            except ValueError:
                return self.request_params['datespan_first']
        else:
            return datetime.utcnow().month

    @property
    def second(self):
        if 'datespan_second' in self.request_params:
            return int(self.request_params['datespan_second'])
        else:
            return datetime.utcnow().year


class MultiReport(MonthWeekMixin, CustomProjectReport, CommtrackReportMixin, ProjectReportParametersMixin):
    title = ''
    report_template_path = "ewsghana/multi_report.html"
    flush_layout = True
    split = True
    exportable = True
    printable = True
    is_exportable = False
    base_template = 'ewsghana/base_template.html'

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
                dm.location_id if dm.location_id else '',
                program_id if program_id else ''
            )

        return url

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
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate,
            enddate=self.datespan.enddate,
            location_id=self.request.GET.get('location_id'),
        )

    def report_filters(self):
        return [f.slug for f in self.fields]

    def fpr_report_filters(self):
        return [f.slug for f in [AsyncLocationFilter, ProductByProgramFilter, EWSDateFilter]]

    @property
    def report_context(self):
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title,
            'split': self.split,
            'r_filters': self.report_filters(),
            'fpr_filters': self.fpr_report_filters(),
            'exportable': self.is_exportable,
            'location_id': self.request.GET.get('location_id'),
            'slugs': filter_slugs_by_role(self.request.couch_user, self.domain)
        }
        return context

    def get_report_context(self, data_provider):
        total_row = []
        headers = []
        rows = []

        if not self.needs_filters and data_provider.show_table:
            headers = data_provider.headers
            rows = data_provider.rows
        if not data_provider.custom_table:
            context = dict(
                report_table=dict(
                    title=data_provider.title,
                    slug=data_provider.slug,
                    headers=headers,
                    rows=rows,
                    total_row=total_row,
                    start_at_row=0,
                    default_rows=data_provider.default_rows,
                    use_datatables=data_provider.use_datatables,
                ),
                show_table=data_provider.show_table,
                show_chart=data_provider.show_chart,
                charts=data_provider.charts if data_provider.show_chart else [],
                chart_span=12,
            )
        else:
            context = dict(
                report_table=dict(),
                show_table=data_provider.show_table,
                show_chart=data_provider.show_chart,
                charts=data_provider.charts if data_provider.show_chart else [],
                rendered_content=data_provider.rendered_content
            )

        return context

    def is_reporting_type(self):
        if not self.report_config.get('location_id'):
            return False
        sql_location = SQLLocation.objects.get(location_id=self.report_config['location_id'], is_archived=False)
        reporting_types = [
            location_type.name
            for location_type in Domain.get_by_name(self.domain).location_types
            if not location_type.administrative
        ]
        return sql_location.location_type.name in reporting_types

    @property
    def export_table(self):
        r = self.report_context['reports'][0]['report_table']
        return [self._export_table(r['title'], r['headers'], r['rows'])]

    # Export for Facility Page Report, which occurs in every multireport
    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        table.insert(0, [SQLLocation.objects.get(location_id=self.report_config['location_id']).name])
        rows = [_unformat_row(row) for row in formatted_rows]
        # Removing html icon tag from MOS column
        for row in rows:
            row[1] = GenericTabularReport._strip_tags(row[1])
        replace = ''

        for k, v in enumerate(table[1]):
            if v != ' ':
                replace = v
            else:
                table[1][k] = replace
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, self._report_info + table]

    @property
    def _report_info(self):
        program_id = self.request.GET.get('filter_by_program')
        return [
            ['Title of report', 'Location', 'Date range', 'Program'],
            [
                self.title,
                self.active_location.name if self.active_location else 'NATIONAL',
                '{} - {}'.format(
                    ews_date_format(self.datespan.startdate),
                    ews_date_format(self.datespan.enddate)
                ),
                'all' if not program_id or program_id == 'all' else Program.get(docid=program_id).name
            ],
            []
        ]


class ProductSelectionPane(EWSData):
    slug = 'product_selection_pane'
    show_table = True
    title = 'Select Products'
    use_datatables = True
    custom_table = True

    def __init__(self, config, hide_columns=True):
        super(ProductSelectionPane, self).__init__(config)
        self.hide_columns = hide_columns

    @property
    def rows(self):
        return []

    @property
    def rendered_content(self):
        locations = get_supply_points(self.config['location_id'], self.config['domain'])
        products = self.unique_products(locations, all=True)
        programs = {program.get_id: program.name for program in Program.by_domain(self.domain)}
        headers = []
        if 'report_type' in self.config:
            from custom.ewsghana.reports.specific_reports.stock_status_report import MonthOfStockProduct
            headers = [h.html for h in MonthOfStockProduct(self.config).headers]

        result = {}
        for idx, product in enumerate(products, start=1):
            program = programs[product.program_id]
            product_dict = {
                'name': product.name,
                'code': product.code,
                'idx': idx if not headers else headers.index(product.code) if product.code in headers else -1,
                'checked': self.config['program'] is None or self.config['program'] == product.program_id
            }
            if program in result:
                result[program]['product_list'].append(product_dict)
                if result[program]['all'] and not product_dict['checked']:
                    result[program]['all'] = False
            else:
                result[program] = {
                    'product_list': [product_dict],
                    'all': product_dict['checked']
                }

        for _, product_dict in result.iteritems():
            product_dict['product_list'].sort(key=lambda prd: prd['name'])

        return render_to_string('ewsghana/partials/product_selection_pane.html', {
            'products_by_program': result,
            'is_rendered_as_email': self.config.get('is_rendered_as_email', False),
            'hide_columns': self.hide_columns
        })
