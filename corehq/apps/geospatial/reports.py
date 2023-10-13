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
from .utils import get_geo_case_property


class BaseCaseMapReport(ProjectReport, CaseListMixin):
    section_name = gettext_noop("Geospatial")

    dispatcher = CaseManagementMapDispatcher

    @property
    def template_context(self):
        # Whatever is specified here can be accessed through initial_page_data
        context = super(BaseCaseMapReport, self).template_context
        context.update({
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
            'case_row_order': {val.html: idx for idx, val in enumerate(self.headers)},
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

    def _get_geo_point(self, case):
        return NotImplementedError()

    def _get_geo_location(self, case):
        geo_point = self._get_geo_point(case)
        if not geo_point:
            return

        try:
            geo_point = GeoPoint.from_string(geo_point, flexible=True)
            return {"lat": geo_point.latitude, "lng": geo_point.longitude}
        except BadValueError:
            return None


class CaseManagementMap(BaseCaseMapReport):
    name = gettext_noop("Case Management Map")
    slug = "case_management_map"

    base_template = "geospatial/map_visualization_base.html"
    report_template_path = "map_visualization.html"

    def default_report_url(self):
        return reverse('geospatial_default', args=[self.request.project.name])

    def _get_geo_point(self, case):
        geo_point = case.get(get_geo_case_property(case.get('domain')))
        return geo_point

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
            coordinates = self._get_geo_location(self.get_case(row))
            cases.append([
                display.case_id,
                coordinates,
                display.case_link
            ])
        return cases


class CaseGroupingReport(BaseCaseMapReport):
    name = gettext_noop('Case Grouping')
    slug = 'case_grouping_map'
    search_class = CaseSearchES

    base_template = 'geospatial/case_grouping_map_base.html'
    report_template_path = 'case_grouping_map.html'

    def _base_query(self):
        # Overrides super()._base_query() to not implement pagination
        # here. It is done later, in self.rows()
        return self.search_class().domain(self.domain)

    def _build_query(self):
        """
        Returns a filtered, unaggregated, unpaginated ESQuery.

        This allows it to be used by `total_cases()`.
        """
        query = super()._build_query()
        return self._filter_query(query)

    def _filter_query(self, query, additional_filters=None):
        """
        If a user-defined polygon (or other GeoShape) is passed in the
        "feature" GET param, adds that as a filter to ``query``.

        If ``additional_filters`` is set, adds those to ``query``.

        It is possible that both, either one, or none are set. If none
        are set, ``query`` is returned unchanged.
        """
        filters_ = [] if additional_filters is None else additional_filters
        # NOTE: Expects GeoShape in request.GET['feature']
        if self.request.GET.get('feature'):
            case_property = get_geo_case_property(self.domain)
            geojson = json.loads(self.request.GET['feature'])
            shape = geojson_to_es_geoshape(geojson)
            relation = 'within' if shape['type'] == 'polygon' else 'intersects'
            filters_.append(filters.geo_shape(
                field=case_property,
                shape=shape,
                relation=relation,
            ))

        if len(filters_) == 1:
            query.nested(CASE_PROPERTIES_PATH, filters_[0])
        elif len(filters_) > 1:
            query.nested(CASE_PROPERTIES_PATH, filters_)
        return query

    def _aggregate_query(self, query):
        """
        Returns ``query`` with geohash grid aggregation applied.
        """
        case_property = get_geo_case_property(self.domain)
        precision = find_precision(query, case_property)
        return apply_geohash_agg(query, case_property, precision)

    def _get_geo_point(self, case):
        case_obj = wrap_case_search_hit(case)
        geo_case_property = get_geo_case_property(case_obj.domain)
        geo_point = case_obj.case_json.get(geo_case_property)
        return geo_point

    @property
    def rows(self):
        """
        Returns paginated cases
        """
        buckets = self._get_buckets(
            self.domain,
            self.shared_pagination_GET_params,
        )
        if not buckets:
            return []
        # Ignore self.pagination.count. It is always treated as 1.
        geohash = buckets[self.pagination.start]['key']
        query_filters = [filters.geo_grid(
            field=get_geo_case_property(self.domain),
            geohash=geohash,
        )]
        cases = []
        query = super()._build_query()
        self._filter_query(query, additional_filters=query_filters)
        es_results = query.run().raw

        for row in es_results['hits'].get('hits', []):
            display = CaseDisplayES(
                self.get_case(row), self.timezone, self.individual
            )
            coordinates = self._get_geo_location(self.get_case(row))
            cases.append([
                display.case_id,
                coordinates,
                display.case_link
            ])
        return cases

    @property
    def total_records(self):
        """
        Returns the number of buckets.

        Pagination count is always treated as 1, so the total number of
        records == the number of pages == the number of buckets.
        """
        buckets = self._get_buckets(
            self.domain,
            self.shared_pagination_GET_params,
        )
        return len(buckets)

    @property
    def shared_pagination_GET_params(self):
        shared_params = super().shared_pagination_GET_params
        shared_params.append(
            {'name': 'feature', 'value': self.request.GET.get('feature')},
        )
        return shared_params

    # quickcache uses shared_pagination_GET_params as part of its key
    # because those determine the results of `query`
    @quickcache(['self.domain', 'self.shared_pagination_GET_params'],
                timeout=15 * 60)
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
