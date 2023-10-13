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
from .es import (
    AGG_NAME,
    apply_geohash_agg,
    find_precision,
    get_bucket_keys_for_page,
)
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # geohash grid precision, set by self._aggregate_query(), read
        # by self.shared_pagination_GET_params()
        self._precision = None

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
        Adds ``additional_filters`` to ``query``. If a user-defined
        polygon (or other GeoShape) is passed in the "feature" GET
        param, adds that as a filter to ``query``.
        """
        # NOTE: Expects GeoShape in request.GET['feature']
        if self.request.GET.get('feature'):
            case_property = get_geo_case_property(self.domain)
            geojson = json.loads(self.request.GET['feature'])
            shape = geojson_to_es_geoshape(geojson)
            relation = 'within' if shape['type'] == 'polygon' else 'intersects'
            if additional_filters:
                additional_filters.append(filters.geo_shape(
                    field=case_property,
                    shape=shape,
                    relation=relation,
                ))
            else:
                query.nested(
                    CASE_PROPERTIES_PATH,
                    filters.geo_shape(
                        field=case_property,
                        shape=shape,
                        relation=relation,
                    )
                )
        if additional_filters:
            query.nested(
                CASE_PROPERTIES_PATH,
                additional_filters
            )
        return query

    def _aggregate_query(self, query):
        """
        Returns ``query`` with geohash grid aggregation applied.

        Also determines ``self._precision`` if it is not set.
        """
        case_property = get_geo_case_property(self.domain)

        if self.request.GET.get('precision'):
            self._precision = int(self.request.GET['precision'])
        else:
            self._precision = find_precision(query, case_property)

        return apply_geohash_agg(query, case_property, self._precision)

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
        bucket_keys, skip = get_bucket_keys_for_page(
            buckets,
            self.pagination.start,
            self.pagination.count,
        )
        if not bucket_keys:
            return []

        # We now have everything we need to build the query that will
        # return the cases for this page.
        case_property = get_geo_case_property(self.domain)
        cases = []
        for geohash in bucket_keys:
            # We fetch each bucket separately to maintain case sequence.
            query = super()._build_query()
            query_filters = [filters.geo_grid(
                field=case_property,
                geohash=geohash,
            )]
            self._filter_query(query, additional_filters=query_filters)
            es_results = query.run().raw

            for row in es_results['hits'].get('hits', []):
                if skip > 0:
                    skip -= 1
                    continue
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
    def shared_pagination_GET_params(self):
        shared_params = super().shared_pagination_GET_params
        shared_params.extend([
            {'name': 'feature', 'value': self.request.GET.get('feature')},
            {'name': 'precision', 'value': self._precision},
        ])
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
