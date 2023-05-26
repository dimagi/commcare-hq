from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_noop

from corehq.apps.geospatial.dispatchers import CaseManagementMapDispatcher
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES


class CaseManagementMap(ProjectReport, CaseListMixin):
    name = gettext_noop("Case Management")
    slug = "case_management_map"
    report_template_path = "map_visualization.html"

    dispatcher = CaseManagementMapDispatcher

    @property
    def template_context(self):
        # Whatever is specified here can be accessed through initial_page_data
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
            # To add coordinates, we need to send it down like this:
            # {"coordinates": {'lng': -91.91399898526271, 'lat': 42.77590015338612}}
            # We should consider passing in a "center_coordinates" fields to center the map
            # to the relavent
            case = {
                "case_id": display.case_id,
                "case_type": display.case_type,
                "name": display.case_name,
            }
            cases.append(case)
        return dict(
            context={"cases": cases},
        )

    @property
    def default_report_url(self):
        return reverse('geospatial_default', args=[self.request.project.name])
