from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_noop
from jsonobject.exceptions import BadValueError

from corehq.apps.geospatial.dispatchers import CaseManagementMapDispatcher
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES
from corehq.apps.reports.standard.cases.case_list_explorer import CaseListExplorer
from couchforms.geopoint import GeoPoint
from .const import GEO_POINT_CASE_PROPERTY
from .models import GeoPolygon



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
    def report_context(self):
        cases = []
        invalid_geo_cases_count = 0

        def _get_geo_location(case):
            geo_point = case.get(GEO_POINT_CASE_PROPERTY)
            if not geo_point:
                return

            try:
                geo_point = GeoPoint.from_string(geo_point, flexible=True)
                return {"lat": geo_point.latitude, "lng": geo_point.longitude}
            except BadValueError:
                return None

        for row in self.es_results['hits'].get('hits', []):
            es_case = self.get_case(row)
            display = CaseDisplayES(es_case, self.timezone, self.individual)

            coordinates = _get_geo_location(es_case)
            if coordinates is None:
                invalid_geo_cases_count += 1
                continue
            # We should consider passing in a "center_coordinates" fields to center the map
            # to the relavent
            case = {
                "case_id": display.case_id,
                "case_type": display.case_type,
                "name": display.case_name,
                "coordinates": coordinates
            }
            cases.append(case)

        invalid_cases_link = self._invalid_geo_cases_report_link if invalid_geo_cases_count else ''

        return dict(
            context={
                "cases": cases,
                "invalid_geo_cases_report_link": invalid_cases_link,
            },
        )

    @property
    def default_report_url(self):
        return reverse('geospatial_default', args=[self.request.project.name])

    @property
    def _invalid_geo_cases_report_link(self):
        # Copy the set of filters to pre-populate the Case List Explorer page's filters
        query = self.request.GET.copy()
        if 'search_query' in query:
            query.pop('search_query')

        query['search_xpath'] = f"{GEO_POINT_CASE_PROPERTY} = ''"
        cle = CaseListExplorer(self.request, domain=self.domain)

        return "{resource}?{query_params}".format(
            resource=cle.get_url(self.domain),
            query_params=query.urlencode(),
        )
