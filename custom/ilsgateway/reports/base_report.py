from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, MonthYearMixin
from custom.ilsgateway.models import OrganizationSummary
from dimagi.utils.decorators.memoized import memoized


class MultiReport(CustomProjectReport, ProjectReportParametersMixin, MonthYearMixin):
    title = ''
    report_template_path = "ilsgateway/multi_report.html"
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
        org_summary = OrganizationSummary.objects.filter(
            date__range=(self.datespan.startdate, self.datespan.enddate),
            supply_point=self.request.GET.get('location_id')
        )
        return dict(
            domain=self.domain,
            org_summary=org_summary[0] if len(org_summary) > 0 else None,
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
        self.data_source = data_provider
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
            ),
            show_table=data_provider.show_table,
            show_chart=data_provider.show_chart,
            charts=data_provider.charts if data_provider.show_chart else [],
            chart_span=12,
            css_class=data_provider.css_class
        )

        return context
