from django.core.urlresolvers import reverse
from corehq import Domain
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.models import Program
from corehq.apps.reports.commtrack.standard import CommtrackReportMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.graph_models import LineChart, MultiBarChart
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.users.models import WebUser, UserRole, CommCareUser
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import Location, SQLLocation
from custom.ewsghana.utils import get_supply_points

REORDER_LEVEL = 1.5
MAXIMUM_LEVEL = 3


def get_url(view_name, text, domain):
    return '<a href="%s">%s</a>' % (reverse(view_name, args=[domain]), text)


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
    def rows(self):
        raise NotImplementedError

    @property
    def sublocations(self):
        location = Location.get(self.config['location_id'])
        if location.children:
            return location.children
        else:
            return [location]

    @property
    def location_types(self):
        return [loc_type.name for loc_type in filter(
                lambda loc_type: not loc_type.administrative,
                Domain.get_by_name(self.config['domain']).location_types
                )]

    @property
    @memoized
    def products(self):
        if self.config['products']:
            return SQLProduct.objects.filter(product_id__in=self.config['products'])
        elif self.config['program']:
            return SQLProduct.objects.filter(program_id=self.config['program'])
        else:
            return []

    def unique_products(self, locations):
        products = list(self.products)
        for loc in locations:
            products.extend(loc.products)
        return sorted(set(products), key=lambda p: p.code)


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

        def _is_admin(user, domain):
            return isinstance(user, WebUser) and user.get_domain_membership(domain).is_admin

        def _is_read_only(user, domain):
            user_role = user.get_role()
            return isinstance(user, WebUser) and user_role == UserRole.get_read_only_role_by_domain(domain)

        def _can_see_reports(user):
            user_role = user.get_role()
            return isinstance(user, CommCareUser) and user_role.permissions.view_reports

        url = super(MultiReport, cls).get_url(domain=domain, render_as=None, kwargs=kwargs)
        request = kwargs.get('request')
        user = getattr(request, 'couch_user', None)
        if user:
            if _is_admin(user, domain):
                loc = SQLLocation.objects.filter(domain=domain, location_type='country')[0]
                url = '%s?location_id=%s' % (url, loc.location_id)
            elif _is_read_only(user, domain) or _can_see_reports(user):
                    dm = user.get_domain_membership(domain)
                    if dm.program_id:
                        program_id = dm.program_id
                    else:
                        program_id = Program.default_for_domain(domain)
                    url = '%s?location_id=%s&program_id=%s' % (
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

    @property
    def report_context(self):
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title,
            'split': self.split,
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
        sql_location = SQLLocation.objects.get(location_id=self.report_config['location_id'])
        reporting_types = [
            location_type.name
            for location_type in Domain.get_by_name(self.domain).location_types
            if not location_type.administrative
        ]
        return sql_location.location_type in reporting_types

    @property
    def export_table(self):
        r = self.report_context['reports'][0]['report_table']
        return [self._export_table(r['title'], r['headers'], r['rows'])]

    # Export for Facility Page Report, which occurs in every multireport
    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        # Removing html icon tag from MOS column
        for row in rows:
            row[1] = GenericTabularReport._strip_tags(row[1])
        replace = ''

        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, table]


class ProductSelectionPane(EWSData):
    slug = 'product_selection_pane'
    show_table = True
    title = 'Product Selection Pane'

    @property
    def rows(self):
        locations = get_supply_points(self.config['location_id'], self.config['domain'])
        products = self.unique_products(locations)
        result = [['<input value=\"{0}\" type=\"checkbox\">{1} ({0})</input>'.format(p.code, p.name)]
                  for p in products]
        result.append(['<button id=\"selection_pane_apply\" class=\"filters btn\">Apply</button>'])
        return result
