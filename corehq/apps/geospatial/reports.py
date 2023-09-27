import json

from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from jsonobject.exceptions import BadValueError

from couchforms.geopoint import GeoPoint

from corehq.apps.case_search.const import CASE_PROPERTIES_PATH
from corehq.apps.es import CaseSearchES, filters
from corehq.apps.es.aggregations import (
    FilterAggregation,
    GeohashGridAggregation,
    NestedAggregation,
)
from corehq.apps.es.case_search import PROPERTY_GEOPOINT_VALUE, PROPERTY_KEY
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES

from .dispatchers import CaseManagementMapDispatcher
from .es import AGG_NAME, find_precision
from .models import GeoPolygon
from .utils import get_geo_case_property


class BaseCaseMap(ProjectReport, CaseListMixin):
    section_name = gettext_noop("Geospatial")

    dispatcher = CaseManagementMapDispatcher

    @property
    def template_context(self):
        # Whatever is specified here can be accessed through initial_page_data
        context = super(BaseCaseMap, self).template_context
        context.update({
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
        })
        return context

    @property
    def headers(self):
        from corehq.apps.reports.datatables import (
            DataTablesColumn,
            DataTablesHeader,
        )
        headers = DataTablesHeader(
            DataTablesColumn(_("case_id"), prop_name="type.exact"),
            DataTablesColumn(_("GPS"), prop_name="type.exact"),
            DataTablesColumn(_("Name"), prop_name="name.exact", css_class="case-name-link"),
        )
        headers.custom_sort = [[2, 'desc']]
        return headers

    @property
    def rows(self):

        def _get_geo_location(case):
            geo_point = case.get(get_geo_case_property(case.get('domain')))
            if not geo_point:
                return

            try:
                geo_point = GeoPoint.from_string(geo_point, flexible=True)
                return {"lat": geo_point.latitude, "lng": geo_point.longitude}
            except BadValueError:
                return None

        cases = []
        for row in self.es_results['hits'].get('hits', []):
            display = CaseDisplayES(
                self.get_case(row), self.timezone, self.individual
            )
            coordinates = _get_geo_location(self.get_case(row))
            cases.append([
                display.case_id,
                coordinates,
                display.case_link
            ])
        return cases


class CaseManagementMap(BaseCaseMap):
    name = gettext_noop("Case Management Map")
    slug = "case_management_map"

    base_template = "geospatial/map_visualization_base.html"
    report_template_path = "map_visualization.html"

    def default_report_url(self):
        return reverse('geospatial_default', args=[self.request.project.name])

    @property
    def template_context(self):
        context = super(CaseManagementMap, self).template_context
        context.update({
            'saved_polygons': [
                {'id': p.id, 'name': p.name, 'geo_json': p.geo_json}
                for p in GeoPolygon.objects.filter(domain=self.domain).all()
            ]
        })
        return context


class CaseGroupingReport(BaseCaseMap):
    name = gettext_noop('Case Grouping')
    slug = 'case_grouping_map'
    search_class = CaseSearchES

    # TODO: We need a separate base template
    base_template = 'geospatial/map_visualization_base.html'
    report_template_path = 'case_grouping_map.html'

    def _build_query(self):
        query = super()._build_query()
        case_property = get_geo_case_property(self.domain)

        # NOTE: ASSUMES polygon is available in request.POST['feature']
        if 'feature' in self.request.POST:
            # Filter cases by a shape set by the user
            geojson = json.loads(self.request.POST['feature'])
            shape = geojson_to_es_geoshape(geojson)
            relation = 'within' if shape['type'] == 'polygon' else 'intersects'
            query.nested(
                CASE_PROPERTIES_PATH,
                filters.geo_shape(
                    field=case_property,
                    shape=shape,
                    relation=relation,
                )
            )

        # Apply geohash grid aggregation
        if 'precision' in self.request.GET:
            precision = self.request.GET['precision']
        else:
            precision = find_precision(query, case_property)

        nested_agg = NestedAggregation('case_properties', CASE_PROPERTIES_PATH)
        filter_agg = FilterAggregation(
            'case_property',
            filters.term(PROPERTY_KEY, case_property),
        )
        geohash_agg = GeohashGridAggregation(
            AGG_NAME,
            PROPERTY_GEOPOINT_VALUE,
            precision,
        )
        query = query.aggregation(
            nested_agg.aggregation(
                filter_agg.aggregation(
                    geohash_agg
                )
            )
        )
        return query


def geojson_to_es_geoshape(geojson):
    """
    Given a GeoJSON dict, returns a GeoJSON Geometry dict, with "type"
    given as an Elasticsearch type (i.e. in lowercase).

    More info:

    * `The GeoJSON specification (RFC 7946) <https://datatracker.ietf.org/doc/html/rfc7946>`_
    * `Elasticsearch types <https://www.elastic.co/guide/en/elasticsearch/reference/5.6/geo-shape.html#input-structure>`_

    """  # noqa: E501
    supported_types = (
        'Point',
        'LineString',
        'Polygon',  # We expect this, but we get the others for free
        'MultiPoint',
        'MultiLineString',
        'MultiPolygon',
        # GeometryCollection is not supported
    )
    assert geojson['geometry']['type'] in supported_types, \
        f"{geojson['geometry']['type']} is not a supported geometry type"
    return {
        'type': geojson['geometry']['type'].lower(),
        'coordinates': geojson['geometry']['coordinates'],
    }
