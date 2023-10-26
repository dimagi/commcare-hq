import json

from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from jsonobject.exceptions import BadValueError

from couchforms.geopoint import GeoPoint

from corehq.apps.case_search.const import CASE_PROPERTIES_PATH
from corehq.apps.es import CaseSearchES, filters
from corehq.apps.es.case_search import wrap_case_search_hit
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES
from corehq.util.quickcache import quickcache

from .dispatchers import CaseManagementMapDispatcher
from .es import AGG_NAME, apply_geohash_agg, find_precision
from .models import GeoPolygon
from .utils import (
    get_geo_case_property,
    features_to_points_list,
)


class BaseCaseMapReport(ProjectReport, CaseListMixin):
    section_name = gettext_noop("Geospatial")

    dispatcher = CaseManagementMapDispatcher

    search_class = CaseSearchES

    @property
    def template_context(self):
        # Whatever is specified here can be accessed through initial_page_data
        context = super(BaseCaseMapReport, self).template_context
        context.update({
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
            'case_row_order': {val.html: idx for idx, val in enumerate(self.headers)},
            'saved_polygons': [
                {'id': p.id, 'name': p.name, 'geo_json': p.geo_json}
                for p in GeoPolygon.objects.filter(domain=self.domain).all()
            ],
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
            DataTablesColumn(_("gps_point"), prop_name="type.exact"),
            DataTablesColumn(_("link"), prop_name="name.exact", css_class="case-name-link"),
        )
        headers.custom_sort = [[2, 'desc']]
        return headers

    def _get_geo_location(self, case):
        geo_case_property = get_geo_case_property(self.domain)
        geo_point = case.get_case_property(geo_case_property)
        if not geo_point:
            return

        try:
            geo_point = GeoPoint.from_string(geo_point, flexible=True)
            return {"lat": geo_point.latitude, "lng": geo_point.longitude}
        except BadValueError:
            return None

    @property
    def rows(self):
        raise NotImplementedError()


class CaseManagementMap(BaseCaseMapReport):
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

    @property
    def rows(self):
        cases = []
        for row in self.es_results['hits'].get('hits', []):
            display = CaseDisplayES(
                self.get_case(row), self.timezone, self.individual
            )
            case = wrap_case_search_hit(row)
            coordinates = self._get_geo_location(case)
            cases.append([
                display.case_id,
                coordinates,
                display.case_link
            ])
        return cases


class CaseGroupingReport(BaseCaseMapReport):
    name = gettext_noop('Case Grouping')
    slug = 'case_grouping_map'

    base_template = 'geospatial/case_grouping_map_base.html'
    report_template_path = 'case_grouping_map.html'

    default_rows = 1
    force_page_size = True

    def _base_query(self):
        # Override function to skip default pagination
        return self.search_class().domain(self.domain)

    @property
    def rows(self):
        """
            Returns cases for the current bucket/page

            Each page is a bucket of filtered cases grouped together.
            We first load all buckets of filtered cases,
            and then find the current bucket via index/page number to get the geohash
            And then we filter cases simply for the geohash corresponding to the bucket
        """
        buckets = self._get_buckets()
        if not buckets:
            return []

        cases = []

        # self.pagination.start is the page number
        bucket = buckets[self.pagination.start]
        geohash = bucket['key']

        query = super()._build_query()
        # ToDo: filter by geohash
        es_results = query.run().raw

        for row in es_results['hits'].get('hits', []):
            display = CaseDisplayES(
                self.get_case(row), self.timezone, self.individual
            )
            case = wrap_case_search_hit(row)
            coordinates = self._get_geo_location(case)
            cases.append([
                display.case_id,
                coordinates,
                display.case_link
            ])
        return cases

    @quickcache(['self.domain', 'self.shared_pagination_GET_params'], timeout=15 * 60)
    def _get_buckets(self):
        query = self._build_query()
        query = self._aggregate_query(query)
        es_results = query.run().raw
        if es_results is None:
            return []
        return (
            es_results['aggregations']
            ['case_properties']
            ['case_property']
            [AGG_NAME]
            ['buckets']
        )

    def _aggregate_query(self, query):
        """
        Returns ``query`` with geohash grid aggregation applied.
        """
        case_property = get_geo_case_property(self.domain)
        if 'precision' in self.request.GET:
            precision = self.request.GET['precision']
        else:
            precision = find_precision(query, case_property)
        return apply_geohash_agg(query, case_property, precision)

    @property
    def total_records(self):
        """
        Returns the number of buckets.

        We are showing buckets of cases so,
        total number of records = number of buckets.
        """
        buckets = self._get_buckets()
        return len(buckets)

    def _build_query(self):
        """
        Returns a filtered, unaggregated, unpaginated ESQuery.
        This allows it to be used by `total_cases()`.
        """
        query = super()._build_query()
        return self._add_geospatial_filters(query)

    def _add_geospatial_filters(self, query):
        """
            If a user-defined polygon (or other GeoShape) is passed in the
            "feature" GET param, adds that as a filter to ``query``.
            If ``additional_filters`` is set, adds those to ``query``.
            It is possible that both, either one, or none are set. If none
            are set, ``query`` is returned unchanged.
        """
        if self.request.GET.get('feature'):
            case_property = get_geo_case_property(self.domain)
            try:
                features = json.loads(self.request.GET['features'])
                points_list = features_to_points_list(features)
                query = query.nested(
                    CASE_PROPERTIES_PATH,
                    filters.geo_shape(
                        field=case_property,
                        points_list=points_list,
                    )
                )
            except json.JSONDecodeError:
                pass
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
