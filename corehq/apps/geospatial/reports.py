from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_noop
from django.utils.translation import gettext as _

from corehq.apps.geospatial.dispatchers import CaseManagementMapDispatcher
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES
from corehq.apps.reports.standard.cases.case_list_explorer import CaseListExplorer
from .const import GEO_POINT_CASE_PROPERTY
from .models import GeoPolygon



def _get_geo_location(case):
    geo_point = case['case_json'].get(GEO_POINT_CASE_PROPERTY)
    if not geo_point:
        return
    try:
        # Update if we need altitude and accuracy
        lat, lon, _alt, _acc = geo_point.split(" ")
        return {"lat": float(lat), "lng": float(lon)}
    except ValueError:
        # Invalid coordinates
        return None


class CaseManagementMap(ProjectReport, CaseListMixin):
    name = gettext_noop("Case Management Map")
    slug = "case_management_map"

    base_template = "geospatial/map_visualization_base.html"
    report_template_path = "map_visualization.html"

    dispatcher = CaseManagementMapDispatcher
    section_name = gettext_noop("Geospatial")

    @property
    def template_context(self):
        # Whatever is specified here can be accessed through initial_page_data
        context = super(CaseManagementMap, self).template_context
        context.update({
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
            'saved_polygons': [
                {'id': p.id, 'name': p.name, 'geo_json': p.geo_json}
                for p in GeoPolygon.objects.filter(domain=self.domain).all()
            ]
        })

        return context

    @property
    def default_report_url(self):
        return reverse('geospatial_default', args=[self.request.project.name])

    @property
    def headers(self):
        from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
        headers = DataTablesHeader(
            DataTablesColumn(_("case_id"), prop_name="type.exact"),
            DataTablesColumn(_("GPS"), prop_name="type.exact"),
            DataTablesColumn(_("Name"), prop_name="name.exact", css_class="case-name-link"),
        )
        headers.custom_sort = [[2, 'desc']]
        return headers

    @property
    def rows(self):
        cases = []
        for row in self.es_results['hits'].get('hits', []):
            display = CaseDisplayES(self.get_case(row), self.timezone, self.individual)
            coordinates = _get_geo_location(self.get_case(row))
            cases.append([
                display.case_id,
                coordinates,
                display.case_link
            ])
        return cases
