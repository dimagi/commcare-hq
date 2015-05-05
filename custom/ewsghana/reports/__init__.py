from datetime import datetime
from django.core.urlresolvers import reverse
from django.db.models import Q
from corehq import Domain
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.models import Program
from corehq.apps.reports.commtrack.standard import CommtrackReportMixin
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.graph_models import LineChart, MultiBarChart
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from custom.ewsghana.filters import ProductByProgramFilter
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import Location, SQLLocation
from custom.ewsghana.utils import get_supply_points
from casexml.apps.stock.models import StockTransaction


def get_url(view_name, text, domain):
    return '<a href="%s">%s</a>' % (reverse(view_name, args=[domain]), text)


def get_url_with_location(view_name, text, location_id, domain):
    return '<a href="%s?location_id=%s">%s</a>' % (reverse(view_name, args=[domain]), location_id, text)


class EWSLineChart(LineChart):
    template_partial = 'ewsghana/partials/ews_line_chart.html'


class EWSMultiBarChart(MultiBarChart):
    template_partial = 'ewsghana/partials/ews_multibar_chart.html'


class EWSData(object):
    show_table = False
    show_chart = False
    title = ''
    slug = ''
    use_datatables = False

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
        return [
            location_type.name
            for location_type in Domain.get_by_name(self.domain).location_types
            if not location_type.administrative
        ]

    @property
    def sublocations(self):
        location = Location.get(self.config['location_id'])
        if location.children:
            return location.children
        else:
            return [location]

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
            locations = SQLLocation.objects.filter(
                Q(parent__parent=location) | Q(parent=location, location_type__name__in=location_types)
            )
        elif location.location_type in location_types:
            locations = SQLLocation.objects.filter(id=location.id)
        else:
            locations = SQLLocation.objects.filter(
                domain=self.domain,
                location_type__name__in=location_types,
                parent=location
            )
        return locations.exclude(supply_point_id__isnull=True).exclude(is_archived=True)

    def supply_points_list(self, location_id=None):
        return self.get_supply_points(location_id).values_list('supply_point_id')

    def reporting_supply_points(self, supply_points=None):
        all_supply_points = self.get_supply_points().values_list('supply_point_id', flat=True)
        supply_points = supply_points if supply_points else all_supply_points
        return StockTransaction.objects.filter(
            case_id__in=supply_points,
            report__date__range=[self.config['startdate'], self.config['enddate']]
        ).distinct('case_id').values_list('case_id', flat=True)

    def datetext(self):
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return "last %d days" % (today - self.config['startdate']).days if today == self.config['enddate'] else\
            "%s to %s" % (self.config['startdate'].strftime("%Y-%m-%d"),
                          self.config['enddate'].strftime("%Y-%m-%d"))

    def all_reporting_locations(self):
        return SQLLocation.objects.filter(
            domain=self.domain, location_type__administrative=False, is_archived=False
        ).values_list('supply_point_id', flat=True)


class MultiReport(CustomProjectReport, CommtrackReportMixin, ProjectReportParametersMixin, DatespanMixin):
    title = ''
    report_template_path = "ewsghana/multi_report.html"
    flush_layout = True
    split = True
    exportable = True
    is_exportable = False
    base_template = 'ewsghana/base_template.html'

    @classmethod
    def get_url(cls, domain=None, render_as=None, **kwargs):

        url = super(MultiReport, cls).get_url(domain=domain, render_as=None, kwargs=kwargs)
        request = kwargs.get('request')
        user = getattr(request, 'couch_user', None)

        if user:
            dm = user.get_domain_membership(domain)
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
        return [f.slug for f in [AsyncLocationFilter, ProductByProgramFilter, DatespanFilter]]

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
        }
        return context

    def get_report_context(self, data_provider):
        total_row = []
        headers = []
        rows = []

        if not self.needs_filters and data_provider.show_table:
            headers = data_provider.headers
            rows = data_provider.rows

        context = dict(
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                headers=headers,
                rows=rows,
                total_row=total_row,
                start_at_row=0,
                use_datatables=data_provider.use_datatables,
            ),
            show_table=data_provider.show_table,
            show_chart=data_provider.show_chart,
            charts=data_provider.charts if data_provider.show_chart else [],
            chart_span=12,
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

        return [export_sheet_name, table]


class ProductSelectionPane(EWSData):
    slug = 'product_selection_pane'
    show_table = True
    title = 'Select Products'
    use_datatables = True

    @property
    def rows(self):
        locations = get_supply_points(self.config['location_id'], self.config['domain'])
        products = self.unique_products(locations, all=True)
        programs = {program.get_id: program.name for program in Program.by_domain(self.domain)}
        headers = []
        if 'report_type' in self.config:
            from custom.ewsghana.reports.specific_reports.stock_status_report import MonthOfStockProduct
            headers = [h.html for h in MonthOfStockProduct(self.config).headers]
        result = [
            [
                '<input class=\"toggle-column\" name=\"{1} ({0})\" data-column={2} value=\"{0}\" type=\"checkbox\"'
                '{3}>{1} ({0})</input>'.format(
                    p.code, p.name, idx if not headers else headers.index(p.code) if p.code in headers else -1,
                    'checked' if self.config['program'] is None or self.config['program'] == p.program_id else ''),
                programs[p.program_id], p.code
            ] for idx, p in enumerate(products, start=1)
        ]

        result.sort(key=lambda r: (r[1], r[2]))

        current_program = result[0][1] if result else ''
        rows = [['<div class="program">%s</div>' % current_program]]
        for r in result:
            if r[1] != current_program:
                rows.append(['<div class="program">%s</div>' % r[1]])
                current_program = r[1]
            rows.append([r[0]])
        return rows
