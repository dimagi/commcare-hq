from datetime import datetime
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from corehq import Domain
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.models import Program
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.graph_models import LineChart, MultiBarChart, PieChart

from custom.ewsghana.filters import EWSRestrictionLocationFilter
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from custom.common import ALL_OPTION
from custom.ewsghana.filters import ProductByProgramFilter, EWSDateFilter
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import SQLLocation, LocationType
from custom.ewsghana.utils import get_descendants, filter_slugs_by_role, ews_date_format, get_products_for_locations, \
    get_products_for_locations_by_program, get_products_for_locations_by_products
from casexml.apps.stock.models import StockTransaction


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
        return self.config.get('location_id') or get_object_or_404(
            SQLLocation, domain=self.domain, location_type__name='country'
        ).location_id

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
            return get_products_for_locations_by_products(locations, self.config['products'])
        elif self.config['program'] and not all:
            return get_products_for_locations_by_program(locations, self.config['program'])
        else:
            return get_products_for_locations(locations)


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


class MultiReport(DatespanMixin, CustomProjectReport, ProjectReportParametersMixin):
    title = ''
    report_template_path = "ewsghana/multi_report.html"
    flush_layout = True
    split = True
    exportable = True
    printable = True
    is_exportable = False
    base_template = 'ewsghana/base_template.html'
    is_rendered_as_email = False
    is_rendered_as_print = False

    @property
    @memoized
    def active_location(self):
        loc_id = self.request_params.get('location_id')
        if loc_id:
            return SQLLocation.objects.get(location_id=loc_id)
        else:
            return get_object_or_404(SQLLocation, location_type__name='country', domain=self.domain)

    @property
    @memoized
    def report_location(self):
        return SQLLocation.objects.get(location_id=self.report_config['location_id'])

    @property
    def report_subtitles(self):
        if self.is_rendered_as_email:
            program = self.request.GET.get('filter_by_program')
            products = self.request.GET.getlist('filter_by_product')
            return mark_safe("""
            <br>For Filters:<br>
            Location: {0}<br>
            Program: {1}<br>
            Product: {2}<br>
            Date range: {3} - {4}
            """.format(
                self.report_location.name,
                Program.get(program).name if program != ALL_OPTION else ALL_OPTION.title(),
                ", ".join(
                    [p.name for p in SQLProduct.objects.filter(product_id__in=products)]
                ) if products != ALL_OPTION and products else ALL_OPTION.title(),
                ews_date_format(self.datespan.startdate_utc),
                ews_date_format(self.datespan.enddate_utc)
            ))
        return None

    def get_stock_transactions(self):
        return StockTransaction.objects.filter(
            case_id__in=list(
                self.report_location.get_descendants().exclude(
                    supply_point_id__isnull=True
                ).values_list('supply_point_id', flat=True)),
            report__date__range=[self.report_config['startdate'], self.report_config['enddate']],
            report__domain=self.domain
        ).order_by('report__date', 'pk')

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

            loc_id = ''
            if dm.location_id:
                location = SQLLocation.objects.get(location_id=dm.location_id)
                if cls.__name__ == "DashboardReport" and not location.location_type.administrative:
                    location = location.parent
                loc_id = location.location_id

            start_date, end_date = EWSDateFilter.last_reporting_period()
            url = '%s?location_id=%s&filter_by_program=%s&startdate=%s&enddate=%s' % (
                url,
                loc_id,
                program_id if program_id else '',
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
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
        return [f.slug for f in [EWSRestrictionLocationFilter, ProductByProgramFilter, EWSDateFilter]]

    @property
    def report_context(self):
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title,
            'subtitle': self.report_subtitles,
            'split': self.split,
            'r_filters': self.report_filters(),
            'fpr_filters': self.fpr_report_filters(),
            'exportable': self.is_exportable,
            'emailable': self.emailable,
            'location_id': self.request.GET.get('location_id'),
            'slugs': filter_slugs_by_role(self.request.couch_user, self.domain),
            'startdate': self.datespan.startdate,
            'enddate': self.datespan.enddate,
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
        location = SQLLocation.objects.get(location_id=self.config['location_id'])
        if location.location_type.administrative:
            locations = get_descendants(self.config['location_id'])
            products = self.unique_products(locations, all=True)
        else:
            products = location.products
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
