from django.utils.translation import gettext_noop
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES
from django.conf import settings
from django.urls import reverse


class CaseManagementMap(ProjectReport, CaseListMixin):
    name = gettext_noop("Case Management")
    slug = "case_management_map"
    # base_template = 'reports/base_template.html'
    report_template_path = "map_visualization.html"

    @property
    def template_context(self):
        context = super(CaseManagementMap, self).template_context
        context.update({
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
        })
        return context

    @property
    def report_context(self):
        cases = []
        for row in self.es_results['hits'].get('hits', []):
            es_case = self.get_case(row)
            display = CaseDisplayES(es_case, self.timezone, self.individual)
            cases.append([display.case_id, display.case_name])
        return dict(
            context={"cases": cases},
        )

    @property
    def default_report_url(self):
        return reverse('reports_home', args=[self.request.project.name])
