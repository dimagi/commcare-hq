from corehq.apps.reports.commtrack.standard import CommtrackReportMixin
from corehq.apps.reports.graph_models import Axis, LineChart
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import Location

REORDER_LEVEL = 1.5
MAXIMUM_LEVEL = 3


class EWSData(object):
    show_table = False
    show_chart = False
    title = ''
    slug = ''

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


class MultiReport(CustomProjectReport, CommtrackReportMixin, ProjectReportParametersMixin, DatespanMixin):
    title = ''
    report_template_path = "ewsghana/multi_report.html"
    flush_layout = True

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
            'title': self.title
        }
        return context

    def get_report_context(self, data_provider):
        total_row = []
        headers = []
        rows = []
        charts = []
        if not self.needs_filters and data_provider.show_table:
            headers = data_provider.headers
            rows = data_provider.rows

        if not self.needs_filters and data_provider.show_chart:
            chart = LineChart("Inventory Management Trends", x_axis=Axis(data_provider.chart_x_label, 'd'),
                              y_axis=Axis(data_provider.chart_y_label, '.1f'))
            for product, value in data_provider.chart_data.iteritems():
                chart.add_dataset(product, value)
            charts.append(chart)

        context = dict(
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                headers=headers,
                rows=rows,
                total_row=total_row,
                start_at_row=0,
            ),
            show_table=data_provider.show_table,
            show_chart=data_provider.show_chart,
            charts=charts,
            chart_span=12,
        )

        return context
