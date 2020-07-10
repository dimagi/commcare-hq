from django.http import Http404

from corehq.apps.reports.views import BaseProjectReportSectionView

from .exceptions import CustomDashboardNotFound
from .metadata import get_custom_dashboard_metadata


class CustomDashboardView(BaseProjectReportSectionView):
    default_template_name = 'reports/custom_dashboard.html'

    @property
    def report_id(self):
        return self.kwargs['report_id']

    @property
    def report_metadata(self):
        return get_custom_dashboard_metadata(self.domain, self.report_id)

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except CustomDashboardNotFound:
            raise Http404

    @property
    def template_name(self):
        # note: this uses `template_name` instead of the more standard django `get_template_names`
        # because HQ overrides `render_to_response` in `BasePageView` for some reason
        return self.report_metadata.template_name or self.default_template_name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'domain': self.domain,
            'report_id': self.report_id,
            'report_metadata': self.report_metadata,
        })
        return context
